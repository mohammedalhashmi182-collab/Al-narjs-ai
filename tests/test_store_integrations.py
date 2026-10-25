"""Salla/Zid multi-tenant integration. HTTP is mocked; nothing here calls a real store."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core import portal_auth
from src.db.session import Base
from src.integrations import http as store_http
from src.integrations import limits
from src.integrations.config import SALLA_SCOPES, enabled
from src.integrations.crypto import StoreTokenKeyError
from src.integrations.intent import classify, extract_reference
from src.integrations.phones import same_phone
from src.integrations.tokens import open_secret, seal
from src.models import ClientProject
from src.models.agent_tools import KnowledgeDoc
from src.models.store_integration import StoreConnection, StorePolicy, StoreWebhookEvent
from src.services import catalog, tenant_reply
from src.services.agent_tools import knowledge_base

TOKEN_A = "salla-access-AAAA"
TOKEN_B = "salla-access-BBBB"
STATUS_A = "خرج للتوصيل"
STATUS_B = "ملغى سرّي"
PHONE_A = "966512345678"
SECRET_SALLA = "salla-whsec-test"  # pragma: allowlist secret
SECRET_ZID = "zid-whsec-test"  # pragma: allowlist secret
TEST_STORE_KEY = Fernet.generate_key().decode()


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    yield session_maker
    await engine.dispose()


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    limits.reset()
    store_http.set_transport(httpx.MockTransport(lambda request: httpx.Response(500, json={"no": "network"})))
    for name in (
        "STORE_INTEGRATIONS_ENABLED", "SALLA_CLIENT_ID", "SALLA_CLIENT_SECRET", "SALLA_WEBHOOK_SECRET",
        "SALLA_REDIRECT_URI", "ZID_CLIENT_ID", "ZID_CLIENT_SECRET", "ZID_WEBHOOK_SECRET", "ZID_REDIRECT_URI",
        "STORE_TOKEN_ENC_KEY", "STORE_TOKEN_ENC_KEY_ID", "STORE_TOKEN_ENC_PREVIOUS_KEYS",
        "ZID_WEBHOOK_ALLOW_UNSIGNED", "TRUSTED_PROXY_HOPS", "STORE_WEBHOOK_MAX_AGE_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("STORE_TOKEN_ENC_KEY", TEST_STORE_KEY)
    yield
    store_http.set_transport(None)
    limits.reset()


def _client(maker, project=None):
    from src.main import app

    app.state.session_factory = maker
    cookies = {}
    if project is not None:
        cookies[portal_auth.COOKIE_NAME] = portal_auth.make_session_token(project)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", cookies=cookies)


async def _project(maker, name="متجر الورد", phone="0555000001"):
    async with maker() as session:
        project = ClientProject(client_name=name, phone=phone, package="bay", status="active")
        session.add(project)
        await session.commit()
        return project


def _sign_salla(raw: bytes) -> str:
    return hmac.new(SECRET_SALLA.encode(), raw, hashlib.sha256).hexdigest()


def _stamp(payload: dict, *, age: timedelta | None = None) -> bytes:
    moment = datetime.now(UTC) if age is None else datetime.now(UTC) - age
    body = dict(payload)
    body["created_at"] = moment.strftime("%Y-%m-%d %H:%M:%S")
    return json.dumps(body).encode()


def _enable(monkeypatch):
    monkeypatch.setenv("STORE_INTEGRATIONS_ENABLED", "true")


def _salla_env(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setenv("SALLA_CLIENT_ID", "salla-cid")
    monkeypatch.setenv("SALLA_CLIENT_SECRET", "salla-csecret-do-not-log")
    monkeypatch.setenv("SALLA_WEBHOOK_SECRET", SECRET_SALLA)
    monkeypatch.setenv("SALLA_REDIRECT_URI", "https://karmaai.online/webhooks/stores/salla/callback")


def _zid_env(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setenv("ZID_CLIENT_ID", "zid-cid")
    monkeypatch.setenv("ZID_CLIENT_SECRET", "zid-csecret-do-not-log")
    monkeypatch.setenv("ZID_WEBHOOK_SECRET", SECRET_ZID)
    monkeypatch.setenv("ZID_REDIRECT_URI", "https://karmaai.online/webhooks/stores/zid/callback")


async def _connect(maker, project, platform, token, *, merchant="111", authorization=None, refresh="refresh-1",
                   expires=None):
    async with maker() as session:
        row = StoreConnection(
            project_id=project.id, platform=platform, merchant_id=merchant, store_name="متجر",
            access_token_enc=seal(token), refresh_token_enc=seal(refresh),
            authorization_enc=seal(authorization) if authorization else None,
            expires_at=expires or datetime(2030, 1, 1, tzinfo=UTC), status="active",
        )
        session.add(row)
        await session.commit()
        return row


def test_flag_defaults_off_and_site_copy_is_on_request_read_only(monkeypatch):
    assert enabled() is False
    assert "write" not in SALLA_SCOPES
    monkeypatch.setenv("STORE_INTEGRATIONS_ENABLED", "true")
    monkeypatch.delenv("STORE_TOKEN_ENC_KEY", raising=False)
    assert enabled() is False
    with pytest.raises(StoreTokenKeyError):
        seal("must-not-derive-from-secret-key")
    bay = catalog.PACKAGES["numuw"]  # "bay" was renamed to "numuw" in Pricing v2
    scope = [item for item in bay.get("scope") or [] if "سلة" in item or "زد" in item]
    coming = [item for item in bay.get("coming") or [] if "سلة" in item or "زد" in item]
    assert scope and not coming
    for item in scope:
        assert "قريباً" not in item and "عند الطلب" in item and "قراءة فقط" in item


def test_phone_match_uses_the_last_nine_digits():
    assert same_phone("0512345678", "+966512345678")
    assert same_phone("٩٦٦٥١٢٣٤٥٦٧٨", "0512345678")
    assert not same_phone("0511111111", "0512345678")
    assert not same_phone("***00", "966512345600")


def test_order_reference_extraction():
    assert extract_reference("وين طلبي ١٢٣٤٥٦٧٨٩") == "123456789"
    assert extract_reference("رقم الطلب: gsQNlvfHmT") == "gsQNlvfHmT"
    assert classify("كم تكلفة الشحن؟")[0] == "policy"
    assert classify("هل عندكم عطر الورد")[0] == "product"


async def test_flag_off_hides_install_and_does_not_call_the_store(maker, monkeypatch):
    project = await _project(maker)
    called = {"n": 0}

    def boom(request):
        called["n"] += 1
        return httpx.Response(500)

    store_http.set_transport(httpx.MockTransport(boom))
    async with _client(maker, project) as client:
        response = await client.get(f"/api/portal/projects/{project.id}/stores/salla/install")
    assert response.status_code == 404
    async with maker() as session:
        loaded = await session.get(ClientProject, project.id)
        draft = await tenant_reply.handle_inbound(session, project=loaded, contact=PHONE_A, text="وين طلبي 123456789")
        await session.commit()
    assert draft is not None and draft.kind == "handoff"
    assert "store_tool" not in (draft.meta or {})
    assert called["n"] == 0


async def test_salla_install_url_uses_documented_host_and_read_scopes(maker, monkeypatch):
    _salla_env(monkeypatch)
    project = await _project(maker)
    async with _client(maker, project) as client:
        response = await client.get(f"/api/portal/projects/{project.id}/stores/salla/install", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    parsed = urlparse(location)
    assert parsed.scheme == "https" and parsed.netloc == "accounts.salla.sa" and parsed.path == "/oauth2/auth"
    query = parse_qs(parsed.query)
    assert query["client_id"] == ["salla-cid"]
    assert query["response_type"] == ["code"]
    assert "client_secret" not in location
    scope = query["scope"][0]
    assert scope == SALLA_SCOPES
    assert "read_write" not in scope and "write" not in scope


async def test_salla_callback_stores_encrypted_tokens_without_pii(maker, monkeypatch, caplog):
    _salla_env(monkeypatch)
    project = await _project(maker)
    secret = "salla-csecret-do-not-log"  # pragma: allowlist secret
    access = "ory_at_plaintext_access"
    email = "merchant-private@example.com"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            assert secret.encode() in request.content
            assert "grant_type=authorization_code" in request.content.decode()
            return httpx.Response(200, json={
                "access_token": access, "refresh_token": "ory_rt_plaintext_refresh", "expires": 1209599,
                "scope": SALLA_SCOPES, "token_type": "bearer",
            })
        if request.url.path == "/oauth2/user/info":
            assert request.headers["authorization"] == f"Bearer {access}"
            return httpx.Response(200, json={"data": {
                "id": 99, "email": email, "mobile": "+966500000111",
                "store": {"id": 847769313, "name": "تين وزيتون"},
            }})
        return httpx.Response(404)

    store_http.set_transport(httpx.MockTransport(handler))
    async with _client(maker, project) as client:
        start = await client.get(f"/api/portal/projects/{project.id}/stores/salla/install", follow_redirects=False)
        state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
        done = await client.get("/webhooks/stores/salla/callback", params={"code": "one-time-code", "state": state})
    assert done.status_code == 200 and "تم ربط المتجر" in done.text
    async with maker() as session:
        row = (await session.execute(select(StoreConnection))).scalar_one()
    blob = " ".join(str(getattr(row, field) or "") for field in (
        "merchant_id", "store_name", "access_token_enc", "refresh_token_enc", "scopes", "store_ref"))
    assert row.merchant_id == "847769313" and row.store_name == "تين وزيتون"
    assert email not in blob and "+966500000111" not in blob and access not in blob
    assert open_secret(row.access_token_enc) == access
    assert secret not in caplog.text and access not in caplog.text


async def test_order_status_requires_the_callers_phone(maker, monkeypatch):
    _enable(monkeypatch)
    project = await _project(maker)
    await _connect(maker, project, "salla", TOKEN_A, merchant="847769313")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.salla.dev"
        assert request.url.path == "/admin/v2/orders"
        assert request.url.params["reference_id"] == "275839672"
        assert request.headers["authorization"] == f"Bearer {TOKEN_A}"
        return httpx.Response(200, json={"data": [{
            "reference_id": 275839672,
            "status": {"name": STATUS_A},
            "customer": {"full_name": "سارة السرية", "mobile_code": "966", "mobile": "512345678"},
        }]})

    store_http.set_transport(httpx.MockTransport(handler))
    async with maker() as session:
        loaded = await session.get(ClientProject, project.id)
        matched = await tenant_reply.handle_inbound(session, project=loaded, contact="0512345678", text="وين طلبي 275839672")
        other = await tenant_reply.handle_inbound(session, project=loaded, contact="966500000000", text="وين طلبي 275839672")
        await session.commit()
    assert matched is not None and matched.kind == "reply" and STATUS_A in matched.draft_text
    assert "سارة" not in matched.draft_text and matched.meta.get("verified") is True
    assert other is not None and other.kind == "reply" and STATUS_A not in (other.draft_text or "")
    assert other.meta.get("verified") is False and other.meta.get("outcome") == "order_unverified"
    assert "سارة" not in (other.draft_text or "")


async def test_tenants_cannot_read_each_others_store(maker, monkeypatch):
    _enable(monkeypatch)
    first = await _project(maker, "الأول", "0555000001")
    second = await _project(maker, "الثاني", "0555000002")
    await _connect(maker, first, "salla", TOKEN_A, merchant="1")
    await _connect(maker, second, "salla", TOKEN_B, merchant="2")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers["authorization"]
        seen.append(auth)
        if auth == f"Bearer {TOKEN_A}":
            return httpx.Response(200, json={"data": [{
                "reference_id": 11111, "status": {"name": STATUS_A},
                "customer": {"mobile_code": "966", "mobile": "512345678"},
            }]})
        return httpx.Response(200, json={"data": [{
            "reference_id": 22222, "status": {"name": STATUS_B},
            "customer": {"mobile_code": "966", "mobile": "598765432"},
        }]})

    store_http.set_transport(httpx.MockTransport(handler))
    async with maker() as session:
        loaded = await session.get(ClientProject, first.id)
        draft = await tenant_reply.handle_inbound(session, project=loaded, contact=PHONE_A, text="حالة الطلب 11111")
        session.add(StorePolicy(project_id=first.id, shipping="شحن الأول فقط"))
        await session.commit()
        other = await session.get(ClientProject, second.id)
        await session.commit()
        foreign = await tenant_reply.handle_inbound(session, project=other, contact="966555555555", text="كم الشحن؟")
        await session.commit()
    assert draft is not None and STATUS_A in draft.draft_text and STATUS_B not in draft.draft_text
    assert seen == [f"Bearer {TOKEN_A}"]
    assert foreign is not None and foreign.kind == "handoff" and "شحن الأول" not in (foreign.draft_text or "")


async def test_policy_comes_only_from_config(maker, monkeypatch):
    _enable(monkeypatch)
    project = await _project(maker)
    async with maker() as session:
        await knowledge_base.add_doc(session, "FAQ", "الشحن مجاني دائمًا من قاعدة المعرفة", project_id=project.id)
        session.add(StorePolicy(project_id=project.id, shipping="الشحن ١٥ ريال ويصل خلال ٣ أيام."))
        loaded = await session.get(ClientProject, project.id)
        answer = await tenant_reply.handle_inbound(session, project=loaded, contact=PHONE_A, text="كم تكلفة الشحن؟")
        both = await tenant_reply.handle_inbound(
            session, project=loaded, contact="966500000002", text="ما سياسة الشحن والاسترجاع؟")
        await session.commit()
    assert answer is not None and "١٥ ريال" in answer.draft_text and "مجاني" not in answer.draft_text
    assert answer.meta.get("store_tool") == "store_policy"
    assert both is not None and both.kind == "handoff" and "١٥ ريال" not in (both.draft_text or "")
    assert both.meta.get("handoff") == "no_policy"
    async with maker() as session:
        assert (await session.execute(select(KnowledgeDoc))).scalar_one().project_id == project.id


async def test_product_lookup_and_zid_headers(maker, monkeypatch):
    _enable(monkeypatch)
    project = await _project(maker)
    await _connect(maker, project, "zid", "zid-manager-token", merchant="507530", authorization="zid-auth-token")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.url.host == "api.zid.sa"
        return httpx.Response(200, json={"results": [{
            "id": "p1", "name": {"ar": "عطر الورد", "en": "Rose"}, "price": 120, "sale_price": 90,
            "quantity": 4, "is_infinite": False, "is_published": True,
        }, {
            "id": "p2", "name": {"ar": "مخفي"}, "is_published": False, "quantity": 3,
        }]})

    store_http.set_transport(httpx.MockTransport(handler))
    async with maker() as session:
        loaded = await session.get(ClientProject, project.id)
        draft = await tenant_reply.handle_inbound(session, project=loaded, contact=PHONE_A, text="هل عندكم عطر الورد")
        await session.commit()
    assert draft is not None and "عطر الورد" in draft.draft_text and "متوفر" in draft.draft_text
    assert "مخفي" not in draft.draft_text and "90" in draft.draft_text
    request = seen[0]
    assert request.url.path == "/v1/products/"
    assert request.url.params["search"] == "عطر الورد"
    assert request.headers["authorization"] == "Bearer zid-auth-token"
    assert request.headers["x-manager-token"] == "zid-manager-token"
    assert request.headers["access-token"] == "zid-manager-token"
    assert request.headers["role"] == "Manager"


async def test_zid_order_search_ignores_a_fuzzy_hit(maker, monkeypatch):
    _enable(monkeypatch)
    project = await _project(maker)
    await _connect(maker, project, "zid", "mgr", merchant="3", authorization="auth")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/managers/store/orders"
        assert request.url.params["search_term"] == "gsQNlvfHmT"
        return httpx.Response(200, json={"orders": [{
            "code": "OTHERCODE", "order_status": {"name": STATUS_B},
            "customer": {"mobile": PHONE_A, "name": "لا يُكشف"},
        }]})

    store_http.set_transport(httpx.MockTransport(handler))
    async with maker() as session:
        loaded = await session.get(ClientProject, project.id)
        draft = await tenant_reply.handle_inbound(session, project=loaded, contact=PHONE_A, text="رقم الطلب gsQNlvfHmT")
        await session.commit()
    assert draft is not None and draft.kind == "reply" and STATUS_B not in (draft.draft_text or "")
    assert draft.meta.get("outcome") == "order_not_found"
    assert "لا يُكشف" not in (draft.draft_text or "")


async def test_salla_refresh_replaces_the_single_use_token(maker, monkeypatch):
    _salla_env(monkeypatch)
    project = await _project(maker)
    await _connect(
        maker, project, "salla", "expired-access", merchant="5", refresh="old-refresh",
        expires=datetime.now(UTC) - timedelta(hours=1),
    )
    refreshed = {"body": ""}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            refreshed["body"] = request.content.decode()
            return httpx.Response(200, json={
                "access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 1209599,
                "token_type": "bearer",
            })
        assert request.headers["authorization"] == "Bearer new-access"
        return httpx.Response(200, json={"data": [{
            "reference_id": 55555, "status": {"name": STATUS_A},
            "customer": {"mobile_code": "966", "mobile": "512345678"},
        }]})

    store_http.set_transport(httpx.MockTransport(handler))
    async with maker() as session:
        loaded = await session.get(ClientProject, project.id)
        draft = await tenant_reply.handle_inbound(session, project=loaded, contact=PHONE_A, text="حالة الطلب 55555")
        row = (await session.execute(select(StoreConnection))).scalar_one()
        await session.commit()
    assert "grant_type=refresh_token" in refreshed["body"] and "old-refresh" in refreshed["body"]
    assert "salla-csecret-do-not-log" in refreshed["body"]
    assert open_secret(row.refresh_token_enc) == "new-refresh"
    assert open_secret(row.access_token_enc) == "new-access"
    assert draft is not None and STATUS_A in draft.draft_text


async def test_salla_webhook_signature_idempotency_and_uninstall(maker, monkeypatch, caplog):
    _salla_env(monkeypatch)
    first = await _project(maker, "أ", "0555000011")
    second = await _project(maker, "ب", "0555000012")
    await _connect(maker, first, "salla", TOKEN_A, merchant="1234509876")
    await _connect(maker, second, "salla", TOKEN_B, merchant="999")
    payload = {"event": "app.uninstalled", "merchant": 1234509876, "data": {"id": 6789012345}}
    raw = _stamp(payload)
    bad = await _post_salla(maker, raw, "0" * 64)
    assert bad.status_code == 401
    ok = await _post_salla(maker, raw, _sign_salla(raw))
    again = await _post_salla(maker, raw, _sign_salla(raw))
    assert ok.status_code == 200 and ok.json()["action"] == "uninstalled"
    assert again.json()["duplicate"] is True
    async with maker() as session:
        rows = list((await session.execute(select(StoreConnection).order_by(StoreConnection.merchant_id))).scalars())
        events = list((await session.execute(select(StoreWebhookEvent))).scalars())
    wiped = next(row for row in rows if row.merchant_id == "1234509876")
    kept = next(row for row in rows if row.merchant_id == "999")
    assert wiped.status == "uninstalled" and wiped.access_token_enc is None and wiped.refresh_token_enc is None
    assert open_secret(kept.access_token_enc) == TOKEN_B
    assert events[0].event_name == "app.uninstalled"
    assert TOKEN_A not in caplog.text and PHONE_A not in caplog.text


async def test_salla_authorize_webhook_updates_known_merchant_only(maker, monkeypatch, caplog):
    _salla_env(monkeypatch)
    project = await _project(maker)
    await _connect(maker, project, "salla", "old-access", merchant="1234509876", refresh="old-refresh")
    fresh = "salla-access-NEW-999"
    payload = {"event": "app.store.authorize", "merchant": 1234509876, "data": {
        "access_token": fresh, "refresh_token": "salla-refresh-NEW-999", "expires": 1893456000,
        "scope": "offline_access orders.read", "token_type": "bearer",
    }}
    raw = _stamp(payload)
    response = await _post_salla(maker, raw, _sign_salla(raw))
    assert response.status_code == 200 and response.json()["action"] == "authorized"
    async with maker() as session:
        row = (await session.execute(select(StoreConnection))).scalar_one()
        event = (await session.execute(select(StoreWebhookEvent))).scalar_one()
    assert open_secret(row.access_token_enc) == fresh
    assert fresh not in (row.access_token_enc or "") and fresh not in (event.event_name or "")
    assert fresh not in caplog.text


async def test_flag_off_ignores_authorize_but_still_uninstalls(maker, monkeypatch):
    monkeypatch.setenv("SALLA_WEBHOOK_SECRET", SECRET_SALLA)
    project = await _project(maker)
    await _connect(maker, project, "salla", TOKEN_A, merchant="42")
    authorize = _stamp({"event": "app.store.authorize", "merchant": 42, "data": {
        "access_token": "should-not-save", "refresh_token": "nope", "expires": 1209599,
    }})
    ignored = await _post_salla(maker, authorize, _sign_salla(authorize))
    assert ignored.status_code == 200 and ignored.json()["ignored"] is True
    async with maker() as session:
        row = (await session.execute(select(StoreConnection))).scalar_one()
    assert open_secret(row.access_token_enc) == TOKEN_A
    uninstall = _stamp({"event": "app.uninstalled", "merchant": 42})
    wiped = await _post_salla(maker, uninstall, _sign_salla(uninstall))
    assert wiped.json()["action"] == "uninstalled"
    async with maker() as session:
        row = (await session.execute(select(StoreConnection))).scalar_one()
    assert row.access_token_enc is None


async def test_zid_webhook_basic_auth_and_uninstall_isolation(maker, monkeypatch):
    _zid_env(monkeypatch)
    monkeypatch.setenv("ZID_WEBHOOK_ALLOW_UNSIGNED", "true")
    first = await _project(maker, "أ", "0555000021")
    second = await _project(maker, "ب", "0555000022")
    await _connect(maker, first, "zid", "m1", merchant="507530", authorization="a1")
    await _connect(maker, second, "zid", "m2", merchant="8", authorization="a2")
    payload = {
        "event_name": "app.market.application.uninstall", "store_id": 507530,
        "store_uuid": "d78468cd-4b44-4fee-a00d-76561f35787c", "merchant_email": "hidden@example.com",
        "merchant_phone_no": "966554349999", "status": "uninstall",
    }
    raw = _stamp(payload)
    bad = await _post_zid(maker, raw, {"authorization": "Basic " + base64.b64encode(b"narjis:wrong").decode()})
    assert bad.status_code == 401
    token = base64.b64encode(f"narjis:{SECRET_ZID}".encode()).decode()
    ok = await _post_zid(maker, raw, {"authorization": f"Basic {token}"})
    assert ok.status_code == 200 and ok.json()["action"] == "uninstalled"
    async with maker() as session:
        rows = list((await session.execute(select(StoreConnection))).scalars())
        event = (await session.execute(select(StoreWebhookEvent))).scalar_one()
    wiped = next(row for row in rows if row.merchant_id == "507530")
    kept = next(row for row in rows if row.merchant_id == "8")
    assert wiped.access_token_enc is None and wiped.authorization_enc is None
    assert open_secret(kept.access_token_enc) == "m2"
    assert "hidden@example.com" not in (event.event_name or "") and "966554349999" not in (event.merchant_id or "")


async def test_zid_webhook_accepts_dashboard_header_and_hmac(maker, monkeypatch, caplog):
    _zid_env(monkeypatch)
    project = await _project(maker)
    await _connect(maker, project, "zid", "m", merchant="507530", authorization="a")
    raw = _stamp({"event_name": "order.status.update", "store_id": 507530})
    blocked = await _post_zid(maker, raw, {"x-zid-webhook-token": SECRET_ZID})
    assert blocked.status_code == 401
    monkeypatch.setenv("ZID_WEBHOOK_ALLOW_UNSIGNED", "true")
    header = await _post_zid(maker, raw, {"x-zid-webhook-token": SECRET_ZID})
    assert header.status_code == 200 and header.json()["action"] == "ignored"
    assert "zid webhook accepted unsigned store_id=507530" in caplog.text
    assert SECRET_ZID not in caplog.text
    monkeypatch.delenv("ZID_WEBHOOK_ALLOW_UNSIGNED", raising=False)
    caplog.clear()
    other = _stamp({"event_name": "product.update", "store_id": 507530})
    digest = hmac.new(SECRET_ZID.encode(), other, hashlib.sha256).hexdigest()
    hmac_response = await _post_zid(maker, other, {"x-zid-signature": digest})
    assert hmac_response.status_code == 200
    assert "accepted unsigned" not in caplog.text
    monkeypatch.setenv("ZID_WEBHOOK_ALLOW_UNSIGNED", "true")
    downgrade = _stamp({"event_name": "order.create", "store_id": 507530})
    bad_sig = "ab" * 32
    rejected = await _post_zid(maker, downgrade, {
        "x-zid-signature": bad_sig, "x-zid-webhook-token": SECRET_ZID,
    })
    assert rejected.status_code == 401


async def test_portal_policy_is_isolated_and_editable(maker, monkeypatch):
    _enable(monkeypatch)
    first = await _project(maker, "أ", "0555000031")
    second = await _project(maker, "ب", "0555000032")
    async with _client(maker, first) as client:
        saved = await client.put(
            f"/api/portal/projects/{first.id}/store/policy",
            json={"shipping": "شحن خاص بالأول", "returns": "خلال ٣ أيام", "payment": "مدى"},
        )
        assert saved.status_code == 200
        assert saved.json()["policy"]["shipping"] == "شحن خاص بالأول"
        stolen = await client.get(f"/api/portal/projects/{second.id}/store")
    assert stolen.status_code == 401
    async with _client(maker, second) as client:
        own = await client.get(f"/api/portal/projects/{second.id}/store")
    assert own.status_code == 200 and own.json()["policy"]["shipping"] == ""
    async with _client(maker, first) as client:
        too_long = await client.put(
            f"/api/portal/projects/{first.id}/store/policy",
            json={"shipping": "س" * 1501},
        )
    assert too_long.status_code == 422


async def test_zid_install_url_and_callback(maker, monkeypatch):
    _zid_env(monkeypatch)
    project = await _project(maker)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={
                "access_token": "manager-plain", "Authorization": "auth-plain",
                "refresh_token": "refresh-plain", "expires_in": 31536000,
            })
        assert request.url.path == "/v1/managers/account/store"
        assert request.headers["x-manager-token"] == "manager-plain"
        assert request.headers["authorization"] == "Bearer auth-plain"
        return httpx.Response(200, json={"store": {
            "id": 507530, "uuid": "d78468cd-4b44-4fee-a00d-76561f35787c",
            "name": "متجر زد", "email": "hidden@example.com",
        }})

    store_http.set_transport(httpx.MockTransport(handler))
    async with _client(maker, project) as client:
        start = await client.get(f"/api/portal/projects/{project.id}/stores/zid/install", follow_redirects=False)
        parsed = urlparse(start.headers["location"])
        assert parsed.netloc == "oauth.zid.sa" and parsed.path == "/oauth/authorize"
        assert "client_secret" not in start.headers["location"]
        state = parse_qs(parsed.query)["state"][0]
        done = await client.get("/webhooks/stores/zid/callback", params={"code": "zid-code", "state": state})
    assert done.status_code == 200
    async with maker() as session:
        row = (await session.execute(select(StoreConnection))).scalar_one()
    assert row.merchant_id == "507530" and row.store_ref == "d78468cd-4b44-4fee-a00d-76561f35787c"
    assert "hidden@example.com" not in (row.store_name or "")
    assert open_secret(row.access_token_enc) == "manager-plain"
    assert open_secret(row.authorization_enc) == "auth-plain"


async def test_masked_marketplace_phone_is_not_revealed(maker, monkeypatch):
    _enable(monkeypatch)
    project = await _project(maker)
    await _connect(maker, project, "zid", "mgr", merchant="3", authorization="auth")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"orders": [{
            "code": "123456", "order_status": {"name": STATUS_A},
            "customer": {"mobile": "***00", "name": "J*** D***"},
        }]})

    store_http.set_transport(httpx.MockTransport(handler))
    async with maker() as session:
        loaded = await session.get(ClientProject, project.id)
        draft = await tenant_reply.handle_inbound(session, project=loaded, contact="966500000000", text="طلب 123456")
        await session.commit()
    assert draft is not None and draft.kind == "reply"
    assert STATUS_A not in (draft.draft_text or "") and "J***" not in (draft.draft_text or "")
    assert draft.meta.get("outcome") == "order_unverified"


async def test_order_lookup_rate_limit_stops_guessing(maker, monkeypatch):
    _enable(monkeypatch)
    project = await _project(maker)
    await _connect(maker, project, "salla", TOKEN_A, merchant="1")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"data": []})

    store_http.set_transport(httpx.MockTransport(handler))
    from src.integrations.service import answer_store_question

    async with maker() as session:
        loaded = await session.get(ClientProject, project.id)
        for n in range(8):
            await answer_store_question(session, loaded, PHONE_A, f"حالة الطلب {100000 + n}")
        limited = await answer_store_question(session, loaded, PHONE_A, "حالة الطلب 999999")
    assert calls["n"] == 8
    assert limited is not None and limited.reason == "rate_limited"


def test_store_token_key_rotates_by_id_and_does_not_use_the_whatsapp_key(monkeypatch):
    old = Fernet.generate_key().decode()
    new = Fernet.generate_key().decode()
    monkeypatch.setenv("STORE_TOKEN_ENC_KEY", old)
    monkeypatch.setenv("STORE_TOKEN_ENC_KEY_ID", "old")
    blob = seal("secret-token")
    assert blob.startswith("v1.old.") and "secret-token" not in blob
    assert tenant_reply.decrypt_token(blob.split(".", 2)[2]) is None
    monkeypatch.setenv("STORE_TOKEN_ENC_KEY", new)
    monkeypatch.setenv("STORE_TOKEN_ENC_KEY_ID", "new")
    monkeypatch.setenv("STORE_TOKEN_ENC_PREVIOUS_KEYS", f"old:{old}")
    assert open_secret(blob) == "secret-token"
    assert seal("next").startswith("v1.new.")
    monkeypatch.delenv("STORE_TOKEN_ENC_PREVIOUS_KEYS")
    assert open_secret(blob) is None


def test_store_migration_does_not_reuse_the_rag_revision():
    from pathlib import Path

    path = Path("alembic/versions/0012_store_integrations.py")
    assert path.is_file()
    assert not Path("alembic/versions/0010_store_integrations.py").exists()
    text = path.read_text(encoding="utf-8")
    assert 'revision: str = "0012"' in text
    assert 'down_revision: str | None = "0011"' in text
    assert "store_oauth_nonces" in text


async def test_oauth_callback_requires_the_matching_portal_session(maker, monkeypatch):
    _salla_env(monkeypatch)
    merchant = await _project(maker, "التاجر", "0555000091")
    other = await _project(maker, "آخر", "0555000092")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if request.url.path == "/oauth2/token":
            return httpx.Response(200, json={
                "access_token": "bound-access", "refresh_token": "bound-refresh", "expires": 100,
            })
        if request.url.path == "/oauth2/user/info":
            return httpx.Response(200, json={"data": {"store": {"id": 555001, "name": "متجر مربوط"}}})
        return httpx.Response(404)

    store_http.set_transport(httpx.MockTransport(handler))
    async with _client(maker, merchant) as client:
        start = await client.get(f"/api/portal/projects/{merchant.id}/stores/salla/install", follow_redirects=False)
        state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    async with _client(maker) as client:
        bare = await client.get("/webhooks/stores/salla/callback", params={"code": "c", "state": state})
    assert bare.status_code == 400 and calls["n"] == 0
    async with _client(maker, other) as client:
        foreign = await client.get("/webhooks/stores/salla/callback", params={"code": "c", "state": state})
    assert foreign.status_code == 400 and calls["n"] == 0
    async with maker() as session:
        loaded = await session.get(ClientProject, merchant.id)
        loaded.portal_token_version = int(loaded.portal_token_version or 0) + 1
        await session.commit()
        revoked = loaded
    async with _client(maker, revoked) as client:
        bumped = await client.get("/webhooks/stores/salla/callback", params={"code": "c", "state": state})
    assert bumped.status_code == 400 and calls["n"] == 0
    async with maker() as session:
        loaded = await session.get(ClientProject, merchant.id)
        loaded.portal_token_version = 0
        await session.commit()
        restored = loaded
    async with _client(maker, restored) as client:
        ok = await client.get("/webhooks/stores/salla/callback", params={"code": "c", "state": state})
        again = await client.get("/webhooks/stores/salla/callback", params={"code": "c", "state": state})
    assert ok.status_code == 200 and again.status_code == 400
    assert calls["n"] == 2
    async with maker() as session:
        row = (await session.execute(select(StoreConnection))).scalar_one()
    assert row.project_id == merchant.id
    assert open_secret(row.access_token_enc) == "bound-access"


async def test_failed_token_exchange_burns_the_oauth_nonce(maker, monkeypatch):
    _salla_env(monkeypatch)
    project = await _project(maker)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"error": "invalid_grant"})

    store_http.set_transport(httpx.MockTransport(handler))
    async with _client(maker, project) as client:
        start = await client.get(f"/api/portal/projects/{project.id}/stores/salla/install", follow_redirects=False)
        state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
        first = await client.get("/webhooks/stores/salla/callback", params={"code": "spent-code", "state": state})
        second = await client.get("/webhooks/stores/salla/callback", params={"code": "spent-code", "state": state})
    assert first.status_code == 400 and second.status_code == 400
    assert calls["n"] == 1
    async with maker() as session:
        assert (await session.execute(select(StoreConnection))).scalar_one_or_none() is None


async def test_webhooks_reject_a_stale_or_unbound_timestamp(maker, monkeypatch):
    _salla_env(monkeypatch)
    _zid_env(monkeypatch)
    project = await _project(maker)
    await _connect(maker, project, "salla", TOKEN_A, merchant="42")
    await _connect(maker, project, "zid", "m", merchant="507530", authorization="a")
    missing = json.dumps({"event": "app.uninstalled", "merchant": 42}).encode()
    assert (await _post_salla(maker, missing, _sign_salla(missing))).status_code == 401
    stale = _stamp({"event": "app.uninstalled", "merchant": 42}, age=timedelta(hours=2))
    assert (await _post_salla(maker, stale, _sign_salla(stale))).status_code == 401
    fresh = _stamp({"event": "order.updated", "merchant": 42})
    assert (await _post_salla(maker, fresh, _sign_salla(fresh))).status_code == 200
    monkeypatch.setenv("ZID_WEBHOOK_ALLOW_UNSIGNED", "true")
    old = _stamp({"event_name": "order.status.update", "store_id": 507530}, age=timedelta(hours=2))
    token = base64.b64encode(f"narjis:{SECRET_ZID}".encode()).decode()
    assert (await _post_zid(maker, old, {"authorization": f"Basic {token}"})).status_code == 401
    signed_old = _stamp({"event_name": "order.status.update", "store_id": 9}, age=timedelta(minutes=30))
    digest = hmac.new(SECRET_ZID.encode(), signed_old, hashlib.sha256).hexdigest()
    forged_clock = await _post_zid(maker, signed_old, {
        "x-zid-signature": digest,
        "x-zid-timestamp": str(int(datetime.now(UTC).timestamp())),
    })
    assert forged_clock.status_code == 401
    async with maker() as session:
        row = (await session.execute(select(StoreConnection).where(StoreConnection.platform == "salla"))).scalar_one()
    assert row.status == "active" and open_secret(row.access_token_enc) == TOKEN_A


async def test_store_rate_limit_uses_the_trusted_proxy_hop(maker, monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "1")
    project = await _project(maker)
    statuses = []
    async with _client(maker, project) as client:
        for n in range(21):
            response = await client.put(
                f"/api/portal/projects/{project.id}/store/policy",
                json={"shipping": "شحن"},
                headers={"x-forwarded-for": f"1.1.1.{n}, 203.0.113.9"},
            )
            statuses.append(response.status_code)
    assert statuses.count(200) == 20 and statuses[-1] == 429
    async with _client(maker, project) as client:
        other = await client.put(
            f"/api/portal/projects/{project.id}/store/policy",
            json={"shipping": "شحن"},
            headers={"x-forwarded-for": "1.1.1.1, 203.0.113.10"},
        )
        spoofed_left = await client.put(
            f"/api/portal/projects/{project.id}/store/policy",
            json={"shipping": "شحن"},
            headers={"x-forwarded-for": "203.0.113.9, 198.51.100.7"},
        )
    assert other.status_code == 200
    assert spoofed_left.status_code == 200


async def _post_salla(maker, raw: bytes, signature: str):
    async with _client(maker) as client:
        return await client.post("/webhooks/stores/salla", content=raw, headers={
            "content-type": "application/json", "x-salla-signature": signature,
        })


async def _post_zid(maker, raw: bytes, headers: dict):
    async with _client(maker) as client:
        return await client.post("/webhooks/stores/zid", content=raw, headers={
            "content-type": "application/json", **headers,
        })


def _basic(user: str, password: str) -> dict:
    return {"authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}


async def test_zid_basic_auth_works_without_the_unsigned_flag(maker, monkeypatch):
    _zid_env(monkeypatch)
    monkeypatch.delenv("ZID_WEBHOOK_ALLOW_UNSIGNED", raising=False)
    project = await _project(maker)
    await _connect(maker, project, "zid", "m", merchant="507530", authorization="a")
    raw = _stamp({"event_name": "order.status.update", "store_id": 507530})
    assert (await _post_zid(maker, raw, _basic("narjis", SECRET_ZID))).status_code == 200
    for headers in ({}, _basic("narjis", "wrong"), _basic("other", SECRET_ZID), _basic("narjis", ""),
                    {"authorization": "Bearer " + SECRET_ZID}, {"x-zid-webhook-token": SECRET_ZID}):
        again = _stamp({"event_name": "order.status.update", "store_id": 507530, "n": len(str(headers))})
        assert (await _post_zid(maker, again, headers)).status_code == 401, headers


async def test_zid_empty_secret_never_authenticates(maker, monkeypatch):
    _zid_env(monkeypatch)
    monkeypatch.setenv("ZID_WEBHOOK_SECRET", "")
    monkeypatch.setenv("ZID_WEBHOOK_ALLOW_UNSIGNED", "true")
    raw = _stamp({"event_name": "order.status.update", "store_id": 1})
    for headers in (_basic("narjis", ""), {"x-zid-webhook-token": ""}, {}):
        assert (await _post_zid(maker, raw, headers)).status_code == 401
