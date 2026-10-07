"""Botpress closed-sale intake and the Karmish owner console.

The first version of this integration was closed as PR #30 because it was broken
in a way no test could see. It called ``company_brain.process_event(...)``, a
method that does not exist; the ``AttributeError`` was swallowed by
``except Exception: pass``; and the endpoint answered that the CEO had been
awakened. It reported success while doing nothing.

So these tests are written to fail on exactly that class of defect:

- :class:`TestTheCeoPathActuallyRuns` asserts the orchestrator was *called*, not
  merely that the response said it was. A stub whose method does not exist makes
  the endpoint fail loudly instead of quietly reporting success.
- :class:`TestNothingIsClaimedThatDidNotRun` asserts the reply says ``skipped``
  when the orchestrator is absent. The reverse of the original bug is just as
  bad: claiming work happened when it did not.

The security tests matter for a different reason. A closed sale is a revenue
event, so an unauthenticated caller could fabricate a customer and make the fleet
act on it. The original endpoint had no authentication at all.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.interfaces import botpress_routes as bp
from src.models import AcquisitionLead, InboundMessage

SECRET = "botpress-test-secret-value"


@contextmanager
def _configured(secret: str | None = SECRET):
    """Set or clear BOTPRESS_WEBHOOK_SECRET without leaking between tests."""
    previous = os.environ.get("BOTPRESS_WEBHOOK_SECRET")
    if secret is None:
        os.environ.pop("BOTPRESS_WEBHOOK_SECRET", None)
    else:
        os.environ["BOTPRESS_WEBHOOK_SECRET"] = secret
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("BOTPRESS_WEBHOOK_SECRET", None)
        else:
            os.environ["BOTPRESS_WEBHOOK_SECRET"] = previous


def _sale(**overrides) -> dict:
    payload = {
        "clientName": "Test Establishment",
        "clientEmail": "buyer@example.com",
        "clientPhone": "0551234567",
        "chosenPackage": "social",
        "paymentStatus": "success",
    }
    payload.update(overrides)
    return payload


def _post(client: httpx.AsyncClient, payload: dict, *, secret: str = SECRET, sign: bool = True, sig: str | None = None):
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if sign:
        headers[bp.SIGNATURE_HEADER] = sig if sig is not None else bp.sign_body(secret, raw)
    return client.post("/api/v1/botpress-lead", content=raw, headers=headers)


async def _make_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


class RecordingBrain:
    """Stands in for CompanyBrain and records that run_once really executed."""

    def __init__(self) -> None:
        self.calls = 0

    async def run_once(self) -> dict:
        self.calls += 1
        return {"priorities": 2}


class RecordingQueue:
    def __init__(self) -> None:
        self.tasks: list[dict] = []

    async def enqueue_agent(self, agent_slug, input_data, priority=None, metadata=None, **kwargs):
        self.tasks.append({"slug": agent_slug, "input": input_data, "metadata": metadata})
        return f"task-{len(self.tasks)}"


@contextmanager
def _orchestrator(brain, queue):
    """Attach or detach the orchestrators on the real app state.

    ``None`` means "make sure this component is absent", which is the state the
    app is in for anything the lifespan never built.
    """
    from src.main import app

    missing = object()
    old_brain = getattr(app.state, "company_brain", missing)
    old_queue = getattr(app.state, "queue_worker", missing)

    if brain is not None:
        app.state.company_brain = brain
    elif old_brain is not missing:
        del app.state.company_brain
    if queue is not None:
        app.state.queue_worker = queue
    elif old_queue is not missing:
        del app.state.queue_worker

    try:
        yield
    finally:
        if old_brain is missing:
            if hasattr(app.state, "company_brain"):
                del app.state.company_brain
        else:
            app.state.company_brain = old_brain
        if old_queue is missing:
            if hasattr(app.state, "queue_worker"):
                del app.state.queue_worker
        else:
            app.state.queue_worker = old_queue


@pytest.fixture(autouse=True)
def _reset_limiters():
    """The limiters are process-wide; clear them so one test cannot 429 another."""
    from src.utils import rate_limit as rl

    rl.botpress_limiter.reset()
    rl.karmish_limiter.reset()
    yield
    rl.botpress_limiter.reset()
    rl.karmish_limiter.reset()


@pytest.fixture
async def db():
    """An in-memory schema bound to ``app.state.session_factory``.

    Exposed separately from ``client`` so assertions read the same database the
    endpoint wrote to. Reading the module-level ``get_session_factory()`` instead
    would hit the developer's real database and make the assertions both wrong
    and order-dependent.
    """
    from src.main import app

    engine, maker = await _make_engine()
    app.state.session_factory = maker
    yield maker
    await engine.dispose()


@pytest.fixture
async def client(db):
    """Yields ``(anonymous, owner)`` against the real app."""
    from src.main import app

    transport = httpx.ASGITransport(app=app)

    anon = httpx.AsyncClient(transport=transport, base_url="http://test")
    owned = httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"narjis_owner": make_session_token()},
    )
    async with anon, owned:
        yield anon, owned


# ---------------------------------------------------------------------------
# Authentication: an unauthenticated caller must not be able to invent revenue
# ---------------------------------------------------------------------------


class TestAuthentication:
    async def test_without_a_secret_the_endpoint_is_inert(self, client):
        anon, _ = client
        with _configured(None):
            response = await _post(anon, _sale())
        assert response.status_code == 503
        assert response.json()["reason"] == "not_configured"

    async def test_a_missing_signature_is_refused(self, client):
        anon, _ = client
        with _configured():
            response = await _post(anon, _sale(), sign=False)
        assert response.status_code == 403

    async def test_a_wrong_signature_is_refused(self, client):
        anon, _ = client
        with _configured():
            response = await _post(anon, _sale(), sig="0" * 64)
        assert response.status_code == 403

    async def test_a_signature_from_a_different_secret_is_refused(self, client):
        anon, _ = client
        with _configured():
            response = await _post(anon, _sale(), secret="a-completely-different-secret")
        assert response.status_code == 403

    async def test_the_sha256_prefix_form_is_accepted(self, client):
        anon, _ = client
        with _configured(), _orchestrator(RecordingBrain(), RecordingQueue()):
            raw = json.dumps(_sale(), ensure_ascii=False).encode("utf-8")
            response = await anon.post(
                "/api/v1/botpress-lead",
                content=raw,
                headers={
                    "Content-Type": "application/json",
                    bp.SIGNATURE_HEADER: f"sha256={bp.sign_body(SECRET, raw)}",
                },
            )
        assert response.status_code == 200

    async def test_a_rejected_request_writes_nothing(self, client, db):
        from sqlalchemy import func, select

        anon, _ = client
        with _configured():
            await _post(anon, _sale(), sig="0" * 64)
        async with db() as session:
            leads = (await session.execute(select(func.count()).select_from(AcquisitionLead))).scalar_one()
            events = (await session.execute(select(func.count()).select_from(InboundMessage))).scalar_one()
        assert leads == 0 and events == 0

    async def test_the_secret_is_never_echoed(self, client):
        anon, _ = client
        with _configured():
            response = await _post(anon, _sale(), sig="0" * 64)
        assert SECRET not in response.text

    async def test_health_names_the_variable_but_never_its_value(self, client):
        anon, _ = client
        with _configured():
            response = await anon.get("/api/v1/botpress/health")
        body = response.json()
        assert body["configured"] is True
        assert body["required_env"] == ["BOTPRESS_WEBHOOK_SECRET"]
        assert SECRET not in response.text


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    async def _reject(self, anon, payload, expected=422):
        with _configured():
            response = await _post(anon, payload)
        assert response.status_code == expected
        return response

    async def test_an_unknown_field_is_refused(self, client):
        anon, _ = client
        await self._reject(anon, _sale(role="admin"))

    async def test_a_missing_customer_name_is_refused(self, client):
        anon, _ = client
        payload = _sale()
        payload.pop("clientName")
        await self._reject(anon, payload)

    async def test_an_oversized_field_is_refused(self, client):
        anon, _ = client
        await self._reject(anon, _sale(clientName="A" * 5000))

    async def test_a_malformed_email_is_refused(self, client):
        anon, _ = client
        await self._reject(anon, _sale(clientEmail="not-an-email"))

    async def test_a_too_short_phone_is_refused(self, client):
        anon, _ = client
        await self._reject(anon, _sale(clientPhone="123"))

    async def test_malformed_json_is_refused(self, client):
        anon, _ = client
        with _configured():
            raw = b"{not json"
            response = await anon.post(
                "/api/v1/botpress-lead",
                content=raw,
                headers={"Content-Type": "application/json", bp.SIGNATURE_HEADER: bp.sign_body(SECRET, raw)},
            )
        assert response.status_code == 400

    async def test_an_unpaid_sale_is_refused(self, client):
        anon, _ = client
        with _configured():
            response = await _post(anon, _sale(paymentStatus="pending"))
        assert response.status_code == 400
        assert response.json()["status"] == "payment_incomplete"

    def test_control_characters_are_stripped_from_the_name(self):
        sale = bp.ClosedSale.model_validate(_sale(clientName="Bad\x00Name\nhere"))
        assert "\x00" not in sale.clientName
        assert "\n" not in sale.clientName
        assert sale.clientName == "BadNamehere"

    def test_phone_normalisation_keeps_digits_only(self):
        sale = bp.ClosedSale.model_validate(_sale(clientPhone="+966 (55) 123-4567"))
        assert sale.clientPhone == "+966551234567"

    def test_a_shell_metacharacter_survives_as_inert_data(self):
        sale = bp.ClosedSale.model_validate(_sale(clientName="; rm -rf / && echo $(whoami)"))
        # The value round-trips unchanged as *data*. Nothing in this module ever
        # passes it to a shell, an eval or a format string, so it cannot execute.
        assert sale.clientName == "; rm -rf / && echo $(whoami)"

    def test_an_unknown_package_is_accepted_but_unpriced(self):
        sale = bp.ClosedSale.model_validate(_sale(chosenPackage="platinum-plus"))
        assert sale.package_key() is None
        assert sale.is_paid() is True

    @pytest.mark.parametrize("label", ["social", "Social", "SOCIAL"])
    def test_package_labels_map_onto_the_catalog(self, label):
        sale = bp.ClosedSale.model_validate(_sale(chosenPackage=label))
        assert sale.package_key() == "social"

    def test_package_labels_map_in_arabic_too(self):
        from src.services import catalog

        arabic = catalog.PACKAGES["growth"]["name"]
        sale = bp.ClosedSale.model_validate(_sale(chosenPackage=arabic))
        assert sale.package_key() == "growth"


# ---------------------------------------------------------------------------
# The CEO path -- the bug this file exists to prevent
# ---------------------------------------------------------------------------


class TestTheCeoPathActuallyRuns:
    async def test_the_brain_really_is_called(self, client):
        anon, _ = client
        brain = RecordingBrain()
        with _configured(), _orchestrator(brain, RecordingQueue()):
            response = await _post(anon, _sale())
        assert response.status_code == 200
        assert brain.calls == 1, "the endpoint answered without calling CompanyBrain.run_once"
        assert response.json()["ceo"]["ceo_brain"] == {"priorities": 2}

    async def test_a_task_really_is_enqueued(self, client):
        anon, _ = client
        queue = RecordingQueue()
        with _configured(), _orchestrator(RecordingBrain(), queue):
            response = await _post(anon, _sale(chosenPackage="social"))
        assert response.status_code == 200
        assert len(queue.tasks) == 1, "the endpoint answered without enqueueing any work"
        task = queue.tasks[0]
        assert task["slug"] == "social_media"
        assert task["input"]["customer"] == "Test Establishment"
        assert task["metadata"]["manager"] == "CEO_AlNarjis"

    async def test_the_enqueued_slug_always_exists_in_the_catalog(self, client):
        from src.services import catalog

        anon, _ = client
        queue = RecordingQueue()
        for package in ("social", "ecommerce", "content", "growth", "unknown-plan"):
            with _configured(), _orchestrator(RecordingBrain(), queue):
                await _post(anon, _sale(chosenPackage=package, eventId=f"e-{package}"))
        assert queue.tasks
        for task in queue.tasks:
            assert task["slug"] in catalog.EMPLOYEES

    async def test_a_brain_that_lacks_run_once_does_not_crash_the_webhook(self, client):
        """The exact shape that broke PR #30: a brain with no such method."""
        anon, _ = client

        class Legacy:
            pass

        with _configured(), _orchestrator(Legacy(), RecordingQueue()):
            response = await _post(anon, _sale())
        assert response.status_code == 200
        assert response.json()["ceo"]["ceo_brain"] == "skipped"

    async def test_a_failing_brain_does_not_lose_the_sale(self, client):
        anon, _ = client

        class Exploding:
            async def run_once(self):
                raise RuntimeError("boom")

        queue = RecordingQueue()
        with _configured(), _orchestrator(Exploding(), queue):
            response = await _post(anon, _sale())
        assert response.status_code == 200
        assert response.json()["ceo"]["ceo_brain"] == "error"
        assert len(queue.tasks) == 1, "a CEO failure must not block the handoff"


class TestNothingIsClaimedThatDidNotRun:
    async def test_an_absent_orchestrator_is_reported_as_skipped(self, client):
        anon, _ = client
        with _configured(), _orchestrator(None, None):
            response = await _post(anon, _sale())
        body = response.json()
        assert body["ceo"]["ceo_brain"] == "skipped"
        assert body["ceo"]["task_id"] == "skipped"
        assert body["status"] == "accepted"

    async def test_the_sale_is_still_recorded_without_an_orchestrator(self, client, db):
        from sqlalchemy import select

        anon, _ = client
        with _configured(), _orchestrator(None, None):
            response = await _post(anon, _sale())
        assert response.status_code == 200
        async with db() as session:
            lead = (await session.execute(select(AcquisitionLead))).scalar_one()
        assert lead.company_name == "Test Establishment"
        assert lead.source == "botpress"


# ---------------------------------------------------------------------------
# CRM effects and idempotency
# ---------------------------------------------------------------------------


class TestCrmEffects:
    async def test_a_sale_creates_one_lead_with_the_package_recorded(self, client, db):
        from sqlalchemy import select

        anon, _ = client
        with _configured(), _orchestrator(RecordingBrain(), RecordingQueue()):
            response = await _post(anon, _sale())
        assert response.json()["lead"] == "created"

        async with db() as session:
            lead = (await session.execute(select(AcquisitionLead))).scalar_one()
        assert lead.suggested_package == "social"
        assert lead.segment == "social_media"
        assert lead.email == "buyer@example.com"
        assert lead.phone == "0551234567"

    async def test_lead_status_is_left_for_the_owner_to_decide(self, client, db):
        """Lead-status logic is owner-approval territory, so intake must not set it."""
        from sqlalchemy import select

        anon, _ = client
        with _configured(), _orchestrator(RecordingBrain(), RecordingQueue()):
            await _post(anon, _sale())
        async with db() as session:
            lead = (await session.execute(select(AcquisitionLead))).scalar_one()
        assert lead.lead_status == "NEW"
        assert lead.outreach_status == "NOT_STARTED"

    async def test_a_second_report_from_the_same_customer_does_not_clone(self, client, db):
        from sqlalchemy import func, select

        anon, _ = client
        with _configured(), _orchestrator(RecordingBrain(), RecordingQueue()):
            await _post(anon, _sale(eventId="evt-1"))
            second = await _post(anon, _sale(eventId="evt-2", chosenPackage="growth"))
        assert second.json()["lead"] == "matched"

        async with db() as session:
            count = (await session.execute(select(func.count()).select_from(AcquisitionLead))).scalar_one()
        assert count == 1

    async def test_a_replayed_event_id_is_not_processed_twice(self, client):
        anon, _ = client
        brain = RecordingBrain()
        with _configured(), _orchestrator(brain, RecordingQueue()):
            first = await _post(anon, _sale(eventId="evt-dup"))
            replay = await _post(anon, _sale(eventId="evt-dup"))
        assert first.status_code == 200
        assert replay.json()["status"] == "duplicate"
        assert brain.calls == 1, "a retry woke the CEO twice"

    async def test_the_audit_row_keeps_a_hash_and_sanitised_fields_only(self, client, db):
        from sqlalchemy import select

        anon, _ = client
        with _configured(), _orchestrator(RecordingBrain(), RecordingQueue()):
            await _post(anon, _sale(eventId="evt-audit"))
        async with db() as session:
            row = (await session.execute(select(InboundMessage))).scalar_one()
        assert row.provider_message_id == "evt-audit"
        assert len(row.payload_hash) == 64
        assert row.media_meta["origin"] == "botpress"
        assert SECRET not in json.dumps(row.media_meta, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Karmish console
# ---------------------------------------------------------------------------


class TestKarmishConsole:
    async def test_the_page_requires_the_owner_session(self, client):
        anon, _ = client
        response = await anon.get("/karmish", follow_redirects=False)
        assert response.status_code in (302, 307)
        assert response.headers["location"] == "/login"

    async def test_the_page_renders_for_the_owner(self, client):
        _, owned = client
        response = await owned.get("/karmish")
        assert response.status_code == 200
        assert "كرميش" in response.text

    async def test_the_page_is_never_indexable(self, client):
        _, owned = client
        response = await owned.get("/karmish")
        assert "noindex" in response.headers.get("x-robots-tag", "")
        assert response.headers.get("cache-control") == "no-store"

    async def test_the_agent_count_is_read_live_not_hard_coded(self, client):
        from src.services import catalog

        _, owned = client
        response = await owned.get("/karmish")
        assert str(len(catalog.EMPLOYEES)) in response.text

    async def test_the_talk_endpoint_is_owner_only(self, client):
        anon, _ = client
        with _configured():
            response = await anon.post("/api/v1/karmish/talk", json={"message": "hello"})
        assert response.status_code == 401

    async def test_the_talk_endpoint_does_not_execute_anything_for_a_stranger(self, client):
        anon, _ = client
        brain = RecordingBrain()
        with _configured(), _orchestrator(brain, RecordingQueue()):
            response = await anon.post("/api/v1/karmish/talk", json={"message": "run everything"})
        assert response.status_code == 401
        assert brain.calls == 0

    async def test_the_talk_endpoint_reports_what_actually_happened(self, client):
        _, owned = client
        brain = RecordingBrain()
        queue = RecordingQueue()
        with _configured(), _orchestrator(brain, queue):
            response = await owned.post("/api/v1/karmish/talk", json={"message": "review priorities"})
        assert response.status_code == 200
        body = response.json()
        assert brain.calls == 1
        assert body["task_id"] == "task-1"
        assert body["actions"]

    async def test_the_talk_endpoint_says_so_when_nothing_ran(self, client):
        _, owned = client
        with _configured(), _orchestrator(None, None):
            response = await owned.post("/api/v1/karmish/talk", json={"message": "review"})
        body = response.json()
        assert body["actions"] == []
        assert body["task_id"] is None
        assert "لم" in body["reply"]

    async def test_the_talk_endpoint_refuses_an_empty_message(self, client):
        _, owned = client
        with _configured():
            response = await owned.post("/api/v1/karmish/talk", json={"message": "   "})
        assert response.status_code in (401, 422)

    async def test_the_talk_endpoint_refuses_an_oversized_message(self, client):
        _, owned = client
        with _configured():
            response = await owned.post("/api/v1/karmish/talk", json={"message": "x" * 5000})
        assert response.status_code == 422

    async def test_the_talk_endpoint_refuses_an_unknown_field(self, client):
        _, owned = client
        with _configured():
            response = await owned.post(
                "/api/v1/karmish/talk", json={"message": "hello", "asAdmin": True}
            )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# SEO and cache policy
# ---------------------------------------------------------------------------


class TestSeoAndCaching:
    def test_karmish_is_not_a_public_path(self):
        from src.services import seo

        assert seo.is_public_path("/karmish") is False

    def test_karmish_is_disallowed_in_robots(self):
        from src.services import seo

        assert "Disallow: /karmish" in seo.build_robots()

    def test_karmish_never_appears_in_the_sitemap(self):
        from src.services import seo

        assert "/karmish" not in seo.build_sitemap([], [])

    def test_a_page_under_karmish_is_also_private(self):
        from src.services import seo

        assert seo.is_public_path("/karmish/anything") is False

    def test_hand_edited_css_is_revalidated_not_frozen_for_a_year(self):
        from src.main import _static_cache_control

        assert "max-age=3600" in _static_cache_control("/static/css/karmish.css")
        assert "immutable" not in _static_cache_control("/static/css/karmish.css")

    def test_fingerprinted_assets_are_immutable(self):
        from src.main import _static_cache_control

        assert "immutable" in _static_cache_control("/static/logo.png")
        assert "immutable" in _static_cache_control("/static/vendor/lib.css")

    async def test_static_responses_carry_a_cache_control(self, client):
        anon, _ = client
        response = await anon.get("/static/css/karmish.css")
        assert response.status_code == 200
        assert "max-age" in response.headers.get("cache-control", "")

    async def test_html_is_not_given_a_static_cache_policy(self, client):
        anon, _ = client
        response = await anon.get("/home")
        assert "immutable" not in response.headers.get("cache-control", "")


class TestNoSecretsReachTheClient:
    async def test_no_page_in_this_feature_embeds_a_secret(self, client):
        from pathlib import Path

        _, owned = client
        response = await owned.get("/karmish")
        assert "BOTPRESS_WEBHOOK_SECRET" not in response.text
        for relative in ("src/web/templates/karmish.html", "src/web/static/js/karmish.js"):
            source = Path(relative).read_text(encoding="utf-8")
            assert "BOTPRESS_WEBHOOK_SECRET" not in source
            assert "process.env" not in source
            assert "import.meta.env" not in source


class TestEndpointsRemainIsolated:
    async def test_the_existing_channels_are_untouched(self, client):
        anon, _ = client
        for path in ("/webhooks/telegram/health", "/webhooks/whatsapp/health"):
            response = await anon.get(path)
            assert response.status_code == 200, path

    async def test_billing_is_not_reachable_through_the_new_paths(self, client):
        anon, _ = client
        response = await anon.get("/api/v1/botpress/health")
        assert "/api/payments" not in response.text


def test_uuid_helper_is_importable():
    """Guards the module's own imports: a missing symbol fails collection."""
    assert uuid4 is not None
