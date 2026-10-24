"""BUILD 0.1 launch-safety regressions: bounded shutdown, no retry while
stopping, Moyasar zero-call hold in ops checks, payment route authorization
and idempotent invoice email on /capture."""

from __future__ import annotations

import asyncio
import socket
import time
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.automation.queue_worker import QueueTask, QueueWorker, TaskStatus
from src.models import Base, ClientProject, Payment
from tests.test_paypal_checkout import _checkout, paypal  # noqa: F401 - fixture

# --------------------------------------------------------------------- queue


class _Agent:
    def __init__(self):
        from types import SimpleNamespace

        self.prompt_templates = {"default": SimpleNamespace(template_text="hi")}
        self.default_parameters = {}
        self.default_model = "fake"


class _Registry:
    def __init__(self, fail=False):
        self.fail = fail

    async def get_agent(self, slug):
        if self.fail:
            raise RuntimeError("agent lookup failed")
        return _Agent()


class _HangingProvider:
    async def complete(self, model, request):
        await asyncio.Event().wait()


def _worker(fail=False, concurrency=1) -> QueueWorker:
    return QueueWorker(_Registry(fail), _HangingProvider(), state_manager=None, concurrency=concurrency)


async def test_stop_is_bounded_and_fails_leftover_tasks():
    w = _worker()
    w.shutdown_timeout = 0.3  # a hanging model call must not hang shutdown
    await w.start()
    running = QueueTask(agent_slug="a", timeout_seconds=3600)
    queued = QueueTask(agent_slug="a", timeout_seconds=3600)
    await w.enqueue(running)
    await w.enqueue(queued)
    await asyncio.sleep(0.2)
    started = time.monotonic()
    await asyncio.wait_for(w.stop(), timeout=5)
    assert time.monotonic() - started < 3
    assert running.status == TaskStatus.FAILED and queued.status == TaskStatus.FAILED
    assert "shutting down" in (queued.error or "")
    assert w._queue._unfinished_tasks == 0 and w._queue.qsize() == 0  # task_done balanced
    assert not w._running_tasks


async def test_failure_while_stopping_is_not_requeued():
    w = _worker(fail=True)
    task = QueueTask(agent_slug="a", max_retries=3)
    await w._queue.put((0, 0, task))
    _, _, got = w._queue.get_nowait()
    w._accepting = False
    await asyncio.wait_for(w._execute_task(got), timeout=1.5)  # no 2s backoff
    assert task.status == TaskStatus.FAILED and "shutting down" in task.error
    assert w._queue.qsize() == 0 and w._queue._unfinished_tasks == 0


def test_testclient_shutdown_with_retrying_task_is_fast(monkeypatch):
    """A task in retry backoff at TestClient exit used to hold shutdown for the
    whole backoff chain (2s + 4s). Measured here; also checks the lifespan
    stops the queue before closing the model provider."""
    from fastapi.testclient import TestClient

    from src.core.model_provider import ModelProvider
    from src.main import app

    order = []
    real_stop, real_close = QueueWorker.stop, ModelProvider.close

    async def stop(self, *a, **kw):
        order.append("queue_stop")
        return await real_stop(self, *a, **kw)

    async def close(self, *a, **kw):
        order.append("provider_close")
        return await real_close(self, *a, **kw)

    monkeypatch.setattr(QueueWorker, "stop", stop)
    monkeypatch.setattr(ModelProvider, "close", close)
    with TestClient(app) as c:
        # Let boot-time KB indexing finish first: cancelling it mid-write leaves
        # the shared SQLite test DB locked for later tests (pre-existing, sqlite-only).
        async def _kb_done():
            for t in asyncio.all_tasks():
                if t.get_name() == "public-kb-index":
                    await asyncio.wait({t}, timeout=10)

        c.portal.call(_kb_done)
        qw = c.app.state.queue_worker
        task = QueueTask(agent_slug="no-such-agent-build01", max_retries=3)
        c.portal.call(qw.enqueue, task)
        deadline = time.monotonic() + 5
        while task.retry_count == 0 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert task.retry_count >= 1  # now sleeping in retry backoff
        started = time.monotonic()
    elapsed = time.monotonic() - started
    print(f"TestClient shutdown with a retrying task: {elapsed:.2f}s")
    assert elapsed < 1.5, elapsed
    assert task.status == TaskStatus.FAILED
    assert order.index("queue_stop") < order.index("provider_close")


# --------------------------------------------------------------------- moyasar hold


async def test_ops_monitor_makes_zero_moyasar_calls_while_on_hold(monkeypatch):
    from src.config import settings as s
    from src.services import ops_monitor, payments

    assert payments.MOYASAR_ON_HOLD is True
    # Fake live-shaped keys: "configured" must not lead to a call.
    monkeypatch.setattr(s, "moyasar_api_secret", "sk_live_" + "x" * 40, raising=False)
    monkeypatch.setattr(s, "moyasar_publishable_key", "pk_live_" + "y" * 40, raising=False)
    monkeypatch.setattr(ops_monitor, "configured_externals", lambda: {"moyasar": True})

    def boom(*a, **kw):
        raise AssertionError("network touched while Moyasar is on hold")

    monkeypatch.setattr(socket, "getaddrinfo", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(httpx.AsyncClient, "send", boom)
    out = await ops_monitor.check_external()  # default real _probe
    assert out["moyasar"]["status"] == "on_hold" and out["moyasar"]["ok"] is None
    direct = await ops_monitor._probe(ops_monitor.EXTERNAL_PROBES["moyasar"])
    assert direct["status"] == "on_hold"


# --------------------------------------------------------------------- payments


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def client(maker):
    from src.main import app

    app.state.session_factory = maker
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _project_payment(maker):
    async with maker() as s:
        project = ClientProject(client_name="Buyer", phone="0555000111", package="bidaya")
        s.add(project)
        await s.flush()
        pay = Payment(amount=10000, package="bidaya", gateway="invoice", status="invoice",
                      project_id=project.id, total_halalas=11500)
        s.add(pay)
        await s.commit()
        return project, pay


async def test_stranger_with_uuid_gets_404(client, maker):
    _, pay = await _project_payment(maker)
    assert (await client.get(f"/api/payments/{pay.id}")).status_code == 404
    assert (await client.post(f"/api/payments/{pay.id}/capture", json={})).status_code == 404
    # Same answer as a payment that does not exist: no existence oracle.
    assert (await client.get(f"/api/payments/{uuid.uuid4()}")).status_code == 404
    # A token for another payment does not open this one.
    from src.core.portal_auth import make_payment_token

    other = {"X-Payment-Token": make_payment_token(uuid.uuid4())}
    assert (await client.get(f"/api/payments/{pay.id}", headers=other)).status_code == 404


async def test_owning_portal_session_and_owner_get_200(client, maker):
    from src.core import portal_auth
    from src.core.owner_auth import make_session_token

    project, pay = await _project_payment(maker)
    client.cookies.set(portal_auth.COOKIE_NAME, portal_auth.make_session_token(project))
    r = await client.get(f"/api/payments/{pay.id}")
    assert r.status_code == 200 and r.json()["payment_id"] == str(pay.id)
    client.cookies.clear()
    client.cookies.set("narjis_owner", make_session_token())
    assert (await client.get(f"/api/payments/{pay.id}")).status_code == 200


async def test_return_flow_and_capture_sends_invoice_once(client, maker, paypal, monkeypatch):  # noqa: F811
    from src.services import email_service

    sent = []

    async def fake_send(payment, **kw):
        sent.append(payment.id)
        return True

    monkeypatch.setattr(email_service, "send_invoice", fake_send)
    data = (await client.post("/api/payments", json={
        "package": "bidaya", "method": "paypal", "customer_name": "Buyer",
        "customer_phone": "0555000111", "customer_email": "buyer@example.test",
        "refund_consent": True,
    }, headers={"idempotency-key": uuid.uuid4().hex})).json()
    # The legit buyer flow: the gateway return URL carries a signed token.
    ret = paypal.last_create["payment_source"]["paypal"]["experience_context"]["return_url"]
    qs = parse_qs(urlparse(ret).query)
    assert qs["id"] == [data["payment_id"]]
    pt = qs["pt"][0]
    pid = data["payment_id"]
    assert (await client.post(f"/api/payments/{pid}/capture", json={})).status_code == 404
    r1 = await client.post(f"/api/payments/{pid}/capture?pt={pt}", json={})
    assert r1.status_code == 200 and r1.json()["status"] == "paid" and r1.json()["email_sent"]
    r2 = await client.post(f"/api/payments/{pid}/capture", headers={"X-Payment-Token": pt}, json={})
    assert r2.status_code == 200 and r2.json()["status"] == "paid"
    assert len(sent) == 1  # repeated capture never re-sends the invoice
    st = await client.get(f"/api/payments/{pid}", headers={"X-Payment-Token": pt})
    assert st.status_code == 200 and st.json()["status"] == "paid"


def test_payment_status_page_forwards_the_return_token():
    from pathlib import Path

    html = Path("src/web/templates/payment_status.html").read_text(encoding="utf-8")
    assert "qp.get('pt')" in html and "X-Payment-Token" in html


async def test_owner_repeated_capture_emails_invoice_once(client, maker, paypal, monkeypatch):  # noqa: F811
    from src.core.owner_auth import make_session_token
    from src.services import email_service

    sent = []

    async def fake_send(payment, **kw):
        sent.append(payment.id)
        return True

    monkeypatch.setattr(email_service, "send_invoice", fake_send)
    data = (await client.post("/api/payments", json={
        "package": "bidaya", "method": "paypal", "customer_name": "Buyer",
        "customer_phone": "0555000111", "customer_email": "buyer@example.test",
        "refund_consent": True,
    }, headers={"idempotency-key": uuid.uuid4().hex})).json()
    client.cookies.set("narjis_owner", make_session_token())
    for _ in range(3):
        r = await client.post(f"/api/payments/{data['payment_id']}/capture", json={})
        assert r.status_code == 200 and r.json()["status"] == "paid"
    assert len(sent) == 1
