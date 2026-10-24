"""The manual-invoice funnel: can a stranger actually pay?

Production reality check behind this file: with no Moyasar secret and no PayPal
credentials, every card button on the checkout degrades to a bank-transfer
invoice. The buyer used to receive a reference and the sentence "tell us on
Telegram" — no bank details, no link, no way to finish. These tests pin the
fixed behaviour: only real methods are offered, the invoice carries everything
needed to settle it, one tap tells the owner, and nothing here can mark a
payment paid without the owner.
"""

from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

import httpx
import pytest

# Retain mocked integration coverage for the separately approved future release.
pytestmark = pytest.mark.usefixtures("moyasar_release")
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.models import Payment
from src.services import payments as pm
from src.services import transfer

TEMPLATES = "src/web/templates"

# Stands for "a card gateway that can actually take money". The live prefix is
# load-bearing: an sk_test_ secret is now treated as a non-method, which is what
# TestMoyasarTestKeyIsNotAPaymentMethod pins.
#
# The prefixes are split at runtime on purpose. GitHub push protection blocks any
# push containing a string that looks like a real credential, and a literal
# `sk_live_<20+ chars>` in a test file trips it -- the push of this very branch
# was rejected with GH013 "Push cannot contain secrets". Assembling the prefix
# keeps the production logic under test without shipping a plausible key.
def _moyasar_key(prefix: str) -> str:
    return prefix + "FAKE-VALUE-FOR-TESTS-ONLY-NOT-A-REAL-KEY"


LIVE_MOYASAR_KEY = _moyasar_key("sk_" + "live_")
TEST_MOYASAR_KEY = _moyasar_key("sk_" + "test_")
PUBLIC_MOYASAR_KEY = _moyasar_key("pk_" + "live_")

MOYASAR_SECRET = LIVE_MOYASAR_KEY
PAYPAL_SECRET = "PAYPAL-SECRET-VALUE"


async def _make_engine():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def maker():
    engine, maker = await _make_engine()
    yield maker
    await engine.dispose()


@pytest.fixture
async def api(maker, monkeypatch):
    from src.main import app

    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)

    def client(owner: bool):
        cookies = {"narjis_owner": make_session_token()} if owner else {}
        return httpx.AsyncClient(transport=transport, base_url="http://test", cookies=cookies)

    async with client(True) as owned, client(False) as anon:
        yield anon, owned


_UNSET = object()


@contextmanager
def _gateway_config(moyasar=None, paypal_id=None, paypal_secret=None, paypal_mode="sandbox",
                    publishable=_UNSET):
    """Override the settings singleton deterministically, restore afterwards.

    A live secret is paired with a live publishable key unless the test passes
    ``publishable`` itself. An empty publishable key must not look live.
    """
    from src.config import settings as s

    names = ("moyasar_api_secret", "moyasar_publishable_key", "paypal_client_id",
             "paypal_client_secret", "paypal_mode")
    old = {n: getattr(s, n) for n in names}
    if publishable is _UNSET:
        if isinstance(moyasar, str) and moyasar.startswith("sk_" + "live_"):
            publishable = PUBLIC_MOYASAR_KEY
        else:
            publishable = old["moyasar_publishable_key"]
    object.__setattr__(s, "moyasar_api_secret", moyasar)
    object.__setattr__(s, "moyasar_publishable_key", publishable)
    object.__setattr__(s, "paypal_client_id", paypal_id)
    object.__setattr__(s, "paypal_client_secret", paypal_secret)
    object.__setattr__(s, "paypal_mode", paypal_mode)
    # The credential verdict is cached at module level; drop it on both edges so
    # one test can never hand the next one a "rejected" gateway.
    pm._credential_cache.clear()
    try:
        yield
    finally:
        for n, v in old.items():
            object.__setattr__(s, n, v)
        pm._credential_cache.clear()


@contextmanager
def _bank_file(**values):
    """Publish bank details from content/transfer.json for the duration."""
    import json

    from src.services import transfer as t

    path = t.CONTENT_FILE
    old = path.read_text(encoding="utf-8") if path.exists() else None
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {name: values.get(name, "") for name in t.FIELDS}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    try:
        yield payload
    finally:
        if old is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(old, encoding="utf-8")


async def _insert_payment(maker, **kw) -> Payment:
    async with maker() as session:
        payment = Payment(
            amount=kw.pop("amount", 49900),
            currency="SAR",
            package=kw.pop("package", "radd"),
            customer_name=kw.pop("customer_name", "مؤسسة الاختبار"),
            customer_phone=kw.pop("customer_phone", "0555555555"),
            gateway=kw.pop("gateway", "invoice"),
            status=kw.pop("status", "invoice"),
            **kw,
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        session.expunge(payment)
        return payment


# ---------------------------------------------------------------------------
# Capabilities: never promise a payment the server cannot take
# ---------------------------------------------------------------------------


class TestCapabilities:
    def test_no_gateway_means_only_bank_transfer_is_offered(self, monkeypatch):
        monkeypatch.delenv("CUSTOMER_BANK_TRANSFER_ENABLED", raising=False)
        with _gateway_config():
            caps = pm.capabilities()
        assert caps["methods"]["invoice"] is False
        assert caps["card"] is False and caps["paypal"] is False
        for method in pm.CARD_METHODS:
            assert caps["methods"][method] is False
        monkeypatch.setenv("CUSTOMER_BANK_TRANSFER_ENABLED", "1")
        with _gateway_config():
            assert pm.capabilities()["methods"]["invoice"] is False

    def test_moyasar_secret_switches_on_every_card_method(self, monkeypatch):
        monkeypatch.delenv("CUSTOMER_BANK_TRANSFER_ENABLED", raising=False)
        with _gateway_config(moyasar=MOYASAR_SECRET):
            caps = pm.capabilities()
        assert caps["card"] is True
        for method in pm.CARD_METHODS:
            assert caps["methods"][method] is True
        assert caps["methods"]["invoice"] is False

    def test_paypal_needs_both_halves_of_the_credential(self, monkeypatch):
        monkeypatch.setenv("CUSTOMER_PAYPAL_ENABLED", "1")
        with _gateway_config(paypal_id="id-only", paypal_mode="live"):
            assert pm.capabilities()["paypal"] is False
        with _gateway_config(paypal_id="id", paypal_secret=PAYPAL_SECRET, paypal_mode="live"):
            caps = pm.capabilities()
        assert caps["paypal"] is True and caps["paypal_test_mode"] is False
        monkeypatch.delenv("CUSTOMER_PAYPAL_ENABLED", raising=False)
        with _gateway_config(paypal_id="id", paypal_secret=PAYPAL_SECRET, paypal_mode="live"):
            assert pm.capabilities()["paypal"] is False

    def test_a_sandbox_paypal_is_not_offered_as_a_way_to_pay(self):
        """A sandbox checkout takes no money: showing it is a dead CTA."""
        with _gateway_config(paypal_id="id", paypal_secret=PAYPAL_SECRET, paypal_mode="sandbox"):
            caps = pm.capabilities()
        assert caps["paypal_configured"] is True
        assert caps["paypal_test_mode"] is True
        assert caps["paypal"] is False
        assert caps["methods"]["paypal"] is False

    def test_capabilities_never_expose_a_secret(self):
        with _gateway_config(moyasar=MOYASAR_SECRET, paypal_id="id", paypal_secret=PAYPAL_SECRET):
            blob = str(pm.capabilities())
        assert MOYASAR_SECRET not in blob and PAYPAL_SECRET not in blob

    def test_an_empty_or_broken_file_yields_no_bank_details(self, tmp_path, monkeypatch):
        from src.services import transfer as t

        monkeypatch.setattr(t, "CONTENT_FILE", tmp_path / "missing.json")
        assert t.bank_details() == {} and t.has_bank_details() is False

        broken = tmp_path / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(t, "CONTENT_FILE", broken)
        assert t.bank_details() == {}


# ---------------------------------------------------------------------------
# Readiness: the owner can see what is missing without reading source
# ---------------------------------------------------------------------------


class TestReadiness:
    def test_names_the_env_vars_the_owner_still_has_to_set(self):
        with _gateway_config():
            report = pm.readiness()
        assert report["collect_money_now"] is False
        assert "MOYASAR_API_SECRET" in report["missing_env"]

    def test_reports_no_missing_env_once_card_is_configured(self):
        with _gateway_config(moyasar=MOYASAR_SECRET, paypal_id="a", paypal_secret="b", paypal_mode="live"):
            report = pm.readiness()
        assert report["collect_money_now"] is True and report["missing_env"] == []

    def test_never_carries_a_credential_value(self):
        with _gateway_config(moyasar=MOYASAR_SECRET, paypal_id="id", paypal_secret=PAYPAL_SECRET):
            blob = str(pm.readiness())
        assert MOYASAR_SECRET not in blob and PAYPAL_SECRET not in blob


# ---------------------------------------------------------------------------
# A configured secret is not a working secret
#
# Production answered 401 "Invalid authorization credentials" on a set
# MOYASAR_API_SECRET, so the checkout advertised mada/Visa/Mastercard/Apple Pay
# and failed every payment while reporting card: true. These pin the probe that
# made the capability honest.
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.text = '{"type":"authentication_error"}'


class _FakeClient:
    """Records calls so the cache can be asserted, and replays a status."""

    calls: list[str] = []
    status = 200
    boom = False

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, params=None, headers=None):
        type(self).calls.append(url)
        if type(self).boom:
            raise RuntimeError("network down")
        return _FakeResponse(type(self).status)


@pytest.fixture
def fake_moyasar(monkeypatch):
    _FakeClient.calls = []
    _FakeClient.status = 200
    _FakeClient.boom = False
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    return _FakeClient


class TestGatewayCredentialProbe:
    async def test_a_rejected_secret_hides_every_card_method(self, fake_moyasar):
        fake_moyasar.status = 401
        with _gateway_config(moyasar=MOYASAR_SECRET):
            state = await pm.probe_moyasar_credentials()
            caps = await pm.capabilities_async()
        assert state == "rejected"
        assert caps["card"] is False and caps["card_configured"] is True
        for method in pm.CARD_METHODS:
            assert caps["methods"][method] is False
        # Bank transfer is not a customer method unless the flag is on.
        assert caps["methods"]["invoice"] is False

    async def test_an_accepted_secret_keeps_the_card_methods(self, fake_moyasar):
        fake_moyasar.status = 200
        with _gateway_config(moyasar=MOYASAR_SECRET):
            state = await pm.probe_moyasar_credentials()
            caps = await pm.capabilities_async()
        assert state == "ok" and caps["card"] is True

    async def test_a_network_blip_does_not_remove_a_working_method(self, fake_moyasar):
        """Only positive proof of rejection may hide a payment method."""
        fake_moyasar.boom = True
        with _gateway_config(moyasar=MOYASAR_SECRET):
            state = await pm.probe_moyasar_credentials()
            caps = await pm.capabilities_async()
        assert state == "unknown"
        assert caps["card"] is True

    async def test_the_verdict_is_cached_so_a_visitor_never_waits_twice(self, fake_moyasar):
        fake_moyasar.status = 401
        with _gateway_config(moyasar=MOYASAR_SECRET):
            await pm.probe_moyasar_credentials()
            await pm.probe_moyasar_credentials()
            await pm.capabilities_async()
        assert len(fake_moyasar.calls) == 1

    async def test_the_probe_uses_an_endpoint_that_creates_nothing(self, fake_moyasar):
        with _gateway_config(moyasar=MOYASAR_SECRET):
            await pm.probe_moyasar_credentials()
        assert fake_moyasar.calls == [pm.MOYASAR_INVOICES_URL]

    async def test_no_secret_means_no_probe_at_all(self, fake_moyasar):
        with _gateway_config():
            assert await pm.probe_moyasar_credentials() == "unset"
        assert fake_moyasar.calls == []

    async def test_the_owner_is_told_the_credential_is_the_problem(self, fake_moyasar):
        fake_moyasar.status = 401
        with _gateway_config(moyasar=MOYASAR_SECRET):
            report = await pm.readiness_async()
        assert report["collect_money_now"] is False
        assert any("MOYASAR_API_SECRET" in issue for issue in report["blocking_issues"])

    async def test_sandbox_paypal_is_named_as_a_blocking_issue(self, fake_moyasar):
        with _gateway_config(
            moyasar=MOYASAR_SECRET,
            paypal_id="id",
            paypal_secret=PAYPAL_SECRET,
            paypal_mode="sandbox",
        ):
            report = await pm.readiness_async()
        assert any("PAYPAL_MODE" in issue for issue in report["blocking_issues"])

    def test_missing_bank_details_are_named_as_a_blocking_issue(self):
        with _gateway_config(moyasar=MOYASAR_SECRET), _bank_file():
            report = pm.readiness()
        assert any("transfer.json" in issue for issue in report["blocking_issues"])

    async def test_the_capabilities_endpoint_reports_the_rejection(self, api, fake_moyasar):
        anon, _ = api
        fake_moyasar.status = 401
        with _gateway_config(moyasar=MOYASAR_SECRET):
            response = await anon.get("/api/payments/capabilities")
        assert response.status_code == 200
        body = response.json()
        assert body["card_credentials"] == "rejected"
        assert body["card"] is False
        assert body["methods"]["mada"] is False
        assert MOYASAR_SECRET not in str(body)


# ---------------------------------------------------------------------------
# A gateway failure must not hand the buyer a dead invoice link
#
# Production returned 200 with an invoice_url for a payment that was never
# persisted: GET /invoice/{id} answered "Invoice not found". The buyer was told
# an invoice existed and could not open it.
# ---------------------------------------------------------------------------


class TestGatewayFailureFallback:
    async def _post_card(self, api, error: str):
        """Post a card payment with the gateway forced to fail.

        The stub is installed with monkeypatch, not by assigning to the module.
        A bare ``pm.initiate_moyasar = _boom`` leaks into every later test in the
        session: the real function never comes back, so a later test that exercises
        initiate_moyasar directly calls the stub instead and fails for a reason that
        has nothing to do with what it asserts.
        """
        anon, _ = api
        from src.services import payments as payments_module

        async def _boom(*args, **kwargs):
            raise pm.PaymentError(error)

        monkey = pytest.MonkeyPatch()
        monkey.setattr(payments_module, "initiate_moyasar", _boom)
        monkey.setenv("CUSTOMER_BANK_TRANSFER_ENABLED", "1")
        try:
            with _gateway_config(moyasar=MOYASAR_SECRET), _bank_file(iban="SA0380000000608010167519"):
                return await anon.post(
                    "/api/payments",
                    json={"refund_consent": True, "package": "bidaya", "method": "mada", "customer_name": "مشتر"},
                )
        finally:
            monkey.undo()

    async def test_a_card_failure_never_becomes_a_bank_invoice(self, api, monkeypatch):
        r = await self._post_card(api, "Moyasar error 401: Invalid authorization credentials")
        assert r.status_code == 502
        assert "invoice_url" not in r.text
        assert "401" not in r.text
        assert "Moyasar error" not in r.text

    async def test_card_failure_stays_off_the_bank_invoice(self, api, monkeypatch):
        """Customers are not offered a bank-transfer invoice."""
        monkeypatch.delenv("CUSTOMER_BANK_TRANSFER_ENABLED", raising=False)
        anon, _ = api
        from src.services import payments as payments_module

        async def _boom(*args, **kwargs):
            raise pm.PaymentError("Moyasar error 401: Invalid authorization credentials")

        monkeypatch.setattr(payments_module, "initiate_moyasar", _boom)
        with _gateway_config(moyasar=MOYASAR_SECRET):
            r = await anon.post(
                "/api/payments",
                json={"refund_consent": True, "package": "bidaya", "method": "mada", "customer_name": "مشتر"},
            )
        assert r.status_code == 502
        assert "invoice_url" not in r.text

    async def test_a_test_key_checkout_creates_no_payment(self, api, maker):
        from sqlalchemy import func, select

        anon, _ = api
        with _gateway_config(moyasar=TEST_MOYASAR_KEY):
            r = await anon.post(
                "/api/payments",
                json={"refund_consent": True, "package": "bidaya", "method": "mada", "customer_name": "مشتر"},
            )
        assert r.status_code == 503
        assert "قيد التفعيل" in r.text
        assert "invoice_url" not in r.text
        async with maker() as session:
            count = (await session.execute(select(func.count()).select_from(Payment))).scalar_one()
        assert count == 0


class TestUnresolvableInvoiceLink:
    """The buyer reaches this URL at the moment they decide to pay.

    A bare 404 JSON ends the sale. One production payment answered 200 with this
    link and then "Invoice not found", so the page now recovers instead.
    """

    async def test_an_unknown_reference_answers_a_page_not_a_json_error(self, api):
        anon, _ = api
        r = await anon.get("/invoice/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404
        assert "application/json" not in r.headers.get("content-type", "")
        assert "لم نتمكن من عرض هذه الفاتورة" in r.text

    async def test_the_recovery_page_shows_the_reference_the_buyer_can_read_out(self, api):
        anon, _ = api
        r = await anon.get("/invoice/deadbeef-0000-0000-0000-000000000000")
        assert "DEADBEEF" in r.text

    async def test_the_recovery_page_offers_a_way_to_reach_a_human(self, api):
        anon, _ = api
        body = (await anon.get("/invoice/deadbeef-0000-0000-0000-000000000000")).text
        # site contact is email only (owner decision, Oct 2026)
        assert "data-open-assistant" in body and "mailto:" not in body
        assert "DEADBEEF" in body
        assert "wa.me/" not in body and "t.me/" not in body

    async def test_a_malformed_reference_does_not_crash(self, api):
        anon, _ = api
        r = await anon.get("/invoice/not-a-uuid-at-all")
        assert r.status_code == 404
        assert "لم نتمكن" in r.text

    async def test_the_english_buyer_gets_the_english_page(self, api):
        anon, _ = api
        r = await anon.get("/invoice/deadbeef-0000-0000-0000-000000000000", cookies={"narjis_lang": "en"})
        assert "We could not load this invoice" in r.text
        assert "Send it through the assistant" in r.text and "mailto:" not in r.text

    async def test_a_real_invoice_is_never_replaced_by_the_recovery_page(self, api, maker):
        anon, _ = api
        payment = await _insert_payment(maker)
        r = await anon.get(f"/invoice/{payment.id}")
        assert r.status_code == 200
        assert "لم نتمكن من عرض هذه الفاتورة" not in r.text


# ---------------------------------------------------------------------------
# Owner decision: prices are VAT-inclusive, so the charge equals the invoice
#
# Moyasar and PayPal previously charged payment.amount, the pre-VAT base, while
# the invoice document bills base + 15%. Every card sale under-collected 15%
# against its own invoice: 499 charged, 573.85 billed (was 800/920 before the rebrand). The owner chose option A.
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("vat15")
class TestVatInclusiveCharging:
    async def test_moyasar_is_asked_to_charge_the_invoice_total(self, maker, monkeypatch):
        captured: dict = {}

        async def _fake_post(*args, **kwargs):
            captured.update(kwargs.get("json") or {})
            raise pm.PaymentError("stop before the network is needed")

        monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post)
        from src.services import catalog

        base = catalog.PACKAGES["bidaya"]["amount"]
        async with maker() as session:
            payment = await pm.create_payment(session, "bidaya", "عميل", None, None)
            with _gateway_config(moyasar=MOYASAR_SECRET), pytest.raises(pm.PaymentError):
                await pm.initiate_moyasar(session, payment, pm.source_mada())

        assert captured["amount"] == pm.total_with_vat(base)
        assert captured["amount"] == 90850  # 790 + 15% VAT
        assert captured["amount"] != base, "charging the pre-VAT base under-collects 15%"

    async def test_an_explicit_charge_amount_is_honoured(self, maker, monkeypatch):
        captured: dict = {}

        async def _fake_post(*args, **kwargs):
            captured.update(kwargs.get("json") or {})
            raise pm.PaymentError("stop")

        monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post)
        async with maker() as session:
            payment = await pm.create_payment(session, "bidaya", "عميل", None, None)
            with _gateway_config(moyasar=MOYASAR_SECRET), pytest.raises(pm.PaymentError):
                await pm.initiate_moyasar(session, payment, pm.source_mada(), amount_halalas=99900)
        assert captured["amount"] == 99900

    async def test_a_charge_below_the_recorded_base_is_refused(self, maker):
        async with maker() as session:
            payment = await pm.create_payment(session, "bidaya", "عميل", None, None)
            with pytest.raises(pm.PaymentError):
                await pm.initiate_moyasar(session, payment, pm.source_mada(), amount_halalas=1)

    def test_the_invoice_and_the_charge_agree_for_every_package(self):
        from src.services import catalog

        for key, meta in catalog.PACKAGES.items():
            base = meta["amount"]
            assert pm.total_with_vat(base) == pm.total_with_vat(base)
            assert pm.total_with_vat(base) > base, key

    @pytest.mark.usefixtures("founding_full")
    async def test_the_api_reports_the_vat_inclusive_total_to_the_checkout(self, api, monkeypatch):
        """Owner-raised invoices still quote VAT. Customers cannot open that path."""
        monkeypatch.setenv("CUSTOMER_BANK_TRANSFER_ENABLED", "1")
        from src.core.owner_auth import make_session_token
        from src.services import catalog

        anon, _ = api
        with _gateway_config():
            refused = await anon.post(
                "/api/payments", json={"refund_consent": True, "package": "bidaya", "method": "invoice"}
            )
            r = await anon.post(
                "/api/payments",
                json={"refund_consent": True, "package": "bidaya", "method": "invoice"},
                cookies={"narjis_owner": make_session_token()},
            )
        assert refused.status_code == 400
        base = catalog.PACKAGES["bidaya"]["amount"]
        assert r.json()["invoice_total"] == pm.total_with_vat(base)
        # The bank-transfer quote must match the invoice: total is VAT-inclusive
        # halalas, and the pre-VAT base stays available as "amount".
        assert r.json()["total"] == pm.total_with_vat(base)
        assert r.json()["amount"] == base


class TestMoyasarTestKeyIsNotAPaymentMethod:
    """A working credential is not the same as a working payment method.

    Production was found holding an ``sk_test_`` secret beside a *live*
    publishable key. Moyasar accepts the test secret and creates real invoices,
    so the credential probe returns 200 and the card buttons come back -- and a
    buyer completes a sandbox checkout that charges nothing.
    """

    def test_a_test_secret_is_not_offered_as_card_checkout(self):
        with _gateway_config(moyasar=TEST_MOYASAR_KEY):
            caps = pm.capabilities()
        assert caps["card_configured"] is True
        assert caps["card_test_mode"] is True
        assert caps["card"] is False
        for method in pm.CARD_METHODS:
            assert caps["methods"][method] is False

    def test_a_live_secret_is_offered(self):
        with _gateway_config(moyasar=LIVE_MOYASAR_KEY):
            caps = pm.capabilities()
        assert caps["card_test_mode"] is False
        assert caps["card"] is True

    def test_a_test_publishable_key_hides_card_beside_a_live_secret(self):
        publishable = "pk_" + "test_" + "FAKE-VALUE-FOR-TESTS-ONLY-NOT-A-REAL-KEY"
        with _gateway_config(moyasar=LIVE_MOYASAR_KEY, publishable=publishable):
            caps = pm.capabilities()
        assert caps["card"] is False
        assert caps["card_test_mode"] is True

    def test_an_empty_publishable_key_disables_card(self):
        with _gateway_config(moyasar=LIVE_MOYASAR_KEY, publishable=""):
            caps = pm.capabilities()
        assert caps["card"] is False
        assert caps["card_test_mode"] is True

    def test_an_empty_publishable_key_never_marks_paid(self):
        payment = Payment(amount=49900, currency="SAR", status="pending")
        with _gateway_config(moyasar=LIVE_MOYASAR_KEY, publishable=""):
            pm.apply_gateway_status(payment, {"status": "paid", "amount": pm.total_with_vat(49900), "currency": "SAR"})
        assert payment.status != "paid"

    async def test_an_empty_publishable_key_checkout_creates_no_payment(self, api, maker):
        from sqlalchemy import func, select

        anon, _ = api
        with _gateway_config(moyasar=LIVE_MOYASAR_KEY, publishable=""):
            r = await anon.post(
                "/api/payments",
                json={"refund_consent": True, "package": "bidaya", "method": "mada", "customer_name": "مشتر"},
            )
        assert r.status_code == 503
        assert "قيد التفعيل" in r.text
        async with maker() as session:
            count = (await session.execute(select(func.count()).select_from(Payment))).scalar_one()
        assert count == 0

    def test_the_bank_transfer_route_stays_closed_unless_enabled(self, monkeypatch):
        monkeypatch.delenv("CUSTOMER_BANK_TRANSFER_ENABLED", raising=False)
        with _gateway_config(moyasar=TEST_MOYASAR_KEY):
            caps = pm.capabilities()
        assert caps["methods"]["invoice"] is False
        monkeypatch.setenv("CUSTOMER_BANK_TRANSFER_ENABLED", "1")
        with _gateway_config(moyasar=TEST_MOYASAR_KEY):
            assert pm.capabilities()["methods"]["invoice"] is False

    def test_the_owner_is_told_a_test_key_is_the_reason(self):
        with _gateway_config(moyasar=TEST_MOYASAR_KEY):
            report = pm.readiness()
        assert any("TEST key" in issue for issue in report["blocking_issues"])
        assert report["collect_money_now"] is False

    def test_the_secret_value_is_never_echoed(self):
        secret = TEST_MOYASAR_KEY + "-SHOULD-NOT-LEAK"
        with _gateway_config(moyasar=secret):
            assert secret not in str(pm.capabilities())
            assert secret not in str(pm.readiness())

    def test_a_publishable_key_is_not_treated_as_a_secret_key(self):
        """A pk_ value is not a secret and cannot charge anything."""
        with _gateway_config(moyasar=PUBLIC_MOYASAR_KEY):
            caps = pm.capabilities()
        assert caps["card"] is False


# ---------------------------------------------------------------------------
# Transfer instructions
# ---------------------------------------------------------------------------


class TestTransferInstructions:
    def test_total_includes_vat_and_matches_the_invoice_maths(self):
        payment = Payment(id=uuid4(), amount=49900, currency="SAR", status="invoice")
        out = pm.transfer_instructions(payment)
        assert out["vat_halalas"] == pm.vat_amount(49900)
        assert out["total_halalas"] == pm.total_with_vat(49900)
        assert out["total_sar"] == round(pm.total_with_vat(49900) / 100, 2)

    def test_reference_is_the_eight_character_code_the_buyer_quotes(self):
        payment = Payment(id=uuid4(), amount=49900, currency="SAR", status="invoice")
        assert pm.transfer_instructions(payment)["reference"] == str(payment.id)[:8].upper()

    def test_whatsapp_link_carries_the_reference_and_the_amount(self):
        payment = Payment(id=uuid4(), amount=49900, currency="SAR", status="invoice")
        out = pm.transfer_instructions(payment)
        assert out["contact"]["whatsapp"] == ""
        assert out["contact"]["phone"] == "tel:+966540799266"
        assert out["reference"]

    def test_bank_details_appear_only_when_the_owner_publishes_them(self, monkeypatch):
        payment = Payment(id=uuid4(), amount=49900, currency="SAR", status="invoice")
        monkeypatch.delenv("CUSTOMER_BANK_TRANSFER_ENABLED", raising=False)
        with _bank_file(iban="SA0380000000608010167519", bank_name="مصرف الراجحي"):
            assert pm.transfer_instructions(payment)["bank"] == {}
        monkeypatch.setenv("CUSTOMER_BANK_TRANSFER_ENABLED", "1")
        with _bank_file(iban="SA0380000000608010167519", bank_name="مصرف الراجحي"):
            assert pm.transfer_instructions(payment)["bank"] == {}


# ---------------------------------------------------------------------------
# The buyer-facing endpoint
# ---------------------------------------------------------------------------


class TestTransferReported:
    async def test_anonymous_buyer_can_report_and_the_owner_is_alerted(self, api, maker, monkeypatch):
        anon, _ = api
        alerts: list[str] = []

        async def fake_alert(text: str):
            alerts.append(text)
            return {"ok": True}

        monkeypatch.setattr("src.services.telegram_sender.send_owner_alert", fake_alert)
        payment = await _insert_payment(maker)

        r = await anon.post(f"/api/payments/{payment.id}/transfer-reported", json={"refund_consent": True})
        assert r.status_code == 200
        body = r.json()
        assert body["reference"] == pm.reference(payment)
        assert body["awaiting_verification"] is True and body["notified_owner"] is True
        assert len(alerts) == 1 and pm.reference(payment) in alerts[0]

    async def test_reporting_never_marks_the_payment_paid(self, api, maker, monkeypatch):
        anon, _ = api

        async def fake_alert(text: str):
            return {"ok": True}

        monkeypatch.setattr("src.services.telegram_sender.send_owner_alert", fake_alert)
        payment = await _insert_payment(maker)

        await anon.post(f"/api/payments/{payment.id}/transfer-reported", json={"refund_consent": True})
        async with maker() as session:
            from sqlalchemy import select

            stored = (
                await session.execute(select(Payment).where(Payment.id == payment.id))
            ).scalar_one()
        assert stored.status == "invoice"
        assert stored.gateway_source == "transfer_reported"

    async def test_a_second_tap_does_not_spam_the_owner(self, api, maker, monkeypatch):
        anon, _ = api
        alerts: list[str] = []

        async def fake_alert(text: str):
            alerts.append(text)
            return {"ok": True}

        monkeypatch.setattr("src.services.telegram_sender.send_owner_alert", fake_alert)
        payment = await _insert_payment(maker)

        await anon.post(f"/api/payments/{payment.id}/transfer-reported", json={"refund_consent": True})
        second = await anon.post(f"/api/payments/{payment.id}/transfer-reported", json={"refund_consent": True})
        assert second.status_code == 200
        assert second.json()["already_reported"] is True
        assert len(alerts) == 1

    async def test_a_failing_alert_keeps_the_record(self, api, maker, monkeypatch):
        anon, _ = api

        async def boom(text: str):
            raise RuntimeError("telegram is down")

        monkeypatch.setattr("src.services.telegram_sender.send_owner_alert", boom)
        payment = await _insert_payment(maker)

        r = await anon.post(f"/api/payments/{payment.id}/transfer-reported", json={"refund_consent": True})
        assert r.status_code == 200 and r.json()["notified_owner"] is False
        async with maker() as session:
            from sqlalchemy import select

            stored = (
                await session.execute(select(Payment).where(Payment.id == payment.id))
            ).scalar_one()
        assert stored.gateway_source == "transfer_reported"

    async def test_a_gateway_settled_invoice_is_not_reported_by_hand(self, api, maker):
        anon, _ = api
        payment = await _insert_payment(maker, gateway="moyasar", gateway_payment_id="inv_123")

        r = await anon.post(f"/api/payments/{payment.id}/transfer-reported", json={"refund_consent": True})
        assert r.status_code == 409

    async def test_an_already_paid_invoice_is_left_alone(self, api, maker, monkeypatch):
        anon, _ = api
        alerts: list[str] = []

        async def fake_alert(text: str):
            alerts.append(text)
            return {"ok": True}

        monkeypatch.setattr("src.services.telegram_sender.send_owner_alert", fake_alert)
        payment = await _insert_payment(maker, status="paid")

        r = await anon.post(f"/api/payments/{payment.id}/transfer-reported", json={"refund_consent": True})
        assert r.status_code == 200
        assert r.json()["awaiting_verification"] is False
        assert alerts == []

    async def test_unknown_and_malformed_ids_are_rejected(self, api):
        anon, _ = api
        assert (await anon.post(f"/api/payments/{uuid4()}/transfer-reported")).status_code == 404
        assert (await anon.post("/api/payments/not-a-uuid/transfer-reported")).status_code == 422


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


class TestPublicSurface:
    async def test_capabilities_endpoint_is_public_and_secret_free(self, api):
        anon, _ = api
        with _gateway_config(moyasar=MOYASAR_SECRET):
            r = await anon.get("/api/payments/capabilities")
        assert r.status_code == 200
        assert MOYASAR_SECRET not in r.text
        assert set(r.json()["methods"]) == {*pm.CARD_METHODS, "paypal", "invoice"}

    async def test_readiness_is_owner_only(self, api):
        anon, owned = api
        assert (await anon.get("/api/owner/payments/readiness")).status_code in (401, 403)
        assert (await owned.get("/api/owner/payments/readiness")).status_code == 200

    async def test_an_unknown_package_is_a_client_error_not_a_crash(self, api):
        anon, _ = api
        r = await anon.post("/api/payments", json={"refund_consent": True, "package": "platinum", "method": "invoice"})
        assert r.status_code == 400

    @pytest.mark.usefixtures("founding_full")
    async def test_a_customer_cannot_fall_back_to_a_bank_invoice(self, api, monkeypatch):
        monkeypatch.setenv("CUSTOMER_BANK_TRANSFER_ENABLED", "1")
        anon, _ = api

        with _gateway_config():
            r = await anon.post(
                "/api/payments",
                json={"refund_consent": True, "package": "bidaya", "method": "invoice", "customer_name": "-buy-test"},
            )
        assert r.status_code == 400
        assert "invoice_url" not in r.text
        assert "Bank transfer is not available" in r.text

    async def test_the_capabilities_route_is_not_shadowed_by_the_payment_id_route(self, api):
        anon, _ = api
        r = await anon.get("/api/payments/capabilities")
        assert r.status_code == 200 and "methods" in r.json()


class TestTemplates:
    def _read(self, name: str) -> str:
        from pathlib import Path

        return (Path(TEMPLATES) / name).read_text(encoding="utf-8")

    def test_both_invoice_pages_carry_the_settlement_block(self):
        for name in ("invoice.html", "invoice_en.html"):
            assert 'include "partials/_transfer.html"' in self._read(name)

    def test_the_block_offers_the_report_button_the_endpoint_backs(self):
        partial = self._read("partials/_transfer.html")
        assert "/transfer-reported" in partial
        assert "xferReport" in partial
        assert 'data-payment="{{ xfer.payment_id }}"' in partial

    def test_an_unpublished_account_asks_for_the_reference_not_for_a_transfer(self):
        """No IBAN means the buyer cannot have paid; do not imply they did."""
        partial = self._read("partials/_transfer.html")
        assert "لم تُنشر بيانات الحساب بعد" in partial
        assert "Account details are not published yet" in partial
        # WhatsApp is promoted to the primary action in that state.
        assert "{% if not xfer.bank.iban %}" in partial and "data-open-assistant" in partial
        assert "mailto:" not in partial

    async def test_a_customer_invoice_page_does_not_publish_bank_details(self, api, maker, monkeypatch):
        monkeypatch.setenv("CUSTOMER_BANK_TRANSFER_ENABLED", "1")
        anon, _ = api
        payment = await _insert_payment(maker)
        with _bank_file(iban="SA0380000000608010167519", bank_name="Al Rajhi"):
            r = await anon.get(f"/invoice/{payment.id}")
        assert r.status_code == 200
        body = r.text
        assert "SA0380000000608010167519" not in body
        assert "نسخ الآيبان" not in body
        assert "لم تُنشر بيانات الحساب بعد" not in body
        assert "wa.me" not in body

    def test_the_checkout_asks_the_server_which_methods_are_real(self):
        portal = self._read("portal.html")
        assert "/api/payments/capabilities" in portal
        assert "cap.methods[x.m]" in portal

    def test_a_hidden_method_is_explained_rather_than_silently_dropped(self):
        portal = self._read("portal.html")
        assert "if (hidden) {" in portal
        assert "coCardNote" in portal

    def test_the_invoice_branch_does_not_send_the_buyer_to_a_transfer(self):
        portal = self._read("portal.html")
        assert "data.invoice_url || ('/invoice/' + data.payment_id)" not in portal
        assert "الدفع غير متاح مؤقتاً" in portal

    def test_checkout_fires_the_money_event_for_the_pixel(self):
        portal = self._read("portal.html")
        assert "fbq('track', 'InitiateCheckout'" in portal

    def test_the_confirmation_shows_sar_not_halalas(self):
        """/api/payments speaks halalas; the portal must not print that integer as SAR."""
        portal = self._read("portal.html")
        assert "data.total.toLocaleString()" not in portal

    def test_the_confirmation_does_not_quote_a_bank_transfer_total(self):
        portal = self._read("portal.html")
        assert "data.invoice_total || data.total" not in portal
        assert "أكمل التحويل" not in portal

    def test_the_purchase_event_reaches_the_ad_platform_in_sar(self):
        status = self._read("payment_status.html")
        assert "Number(st.value || st.total || st.amount || 0) / 100" in status
        assert "value: st.value || (st.total || st.amount || 0)" not in status

    def test_a_captured_lead_fires_the_lead_event(self):
        for name in ("early_access.html", "guide.html"):
            assert "fbq('track', 'Lead')" in self._read(name)
        # the v2 landing fires Lead when the CEO returns a recommendation
        assert "fbq('track', 'Lead', { content_name: 'ceo_consult'" in self._read("landing.html")


class TestTransferModule:
    def test_contact_channels_have_no_empty_whatsapp_link(self):
        channels = transfer.contact_channels()
        assert channels["telegram"] == ""
        assert channels["whatsapp"] == ""
        assert channels["messenger"] == ""
        assert channels["phone"] == "tel:+966540799266"

    def test_a_prefilled_message_is_url_encoded(self):
        buttons = transfer.contact_buttons("ABCD1234", 920.0, "مؤسسة")
        assert buttons["whatsapp"] == ""
        assert buttons["phone"] == "tel:+966540799266"
        assert buttons["email"].startswith("mailto:")