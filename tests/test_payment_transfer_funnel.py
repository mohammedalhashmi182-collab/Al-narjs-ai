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
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.models import Payment
from src.services import payments as pm
from src.services import transfer

TEMPLATES = "src/web/templates"

MOYASAR_SECRET = "sk_test_MOYASAR-SECRET-VALUE"
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


@contextmanager
def _gateway_config(moyasar=None, paypal_id=None, paypal_secret=None, paypal_mode="sandbox"):
    """Override the settings singleton deterministically, restore afterwards."""
    from src.config import settings as s

    names = ("moyasar_api_secret", "paypal_client_id", "paypal_client_secret", "paypal_mode")
    old = {n: getattr(s, n) for n in names}
    object.__setattr__(s, "moyasar_api_secret", moyasar)
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
            amount=kw.pop("amount", 80000),
            currency="SAR",
            package=kw.pop("package", "growth"),
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
    def test_no_gateway_means_only_bank_transfer_is_offered(self):
        with _gateway_config():
            caps = pm.capabilities()
        assert caps["methods"]["invoice"] is True
        assert caps["card"] is False and caps["paypal"] is False
        for method in pm.CARD_METHODS:
            assert caps["methods"][method] is False

    def test_moyasar_secret_switches_on_every_card_method(self):
        with _gateway_config(moyasar=MOYASAR_SECRET):
            caps = pm.capabilities()
        assert caps["card"] is True
        for method in pm.CARD_METHODS:
            assert caps["methods"][method] is True
        assert caps["methods"]["invoice"] is True

    def test_paypal_needs_both_halves_of_the_credential(self):
        with _gateway_config(paypal_id="id-only", paypal_mode="live"):
            assert pm.capabilities()["paypal"] is False
        with _gateway_config(paypal_id="id", paypal_secret=PAYPAL_SECRET, paypal_mode="live"):
            caps = pm.capabilities()
        assert caps["paypal"] is True and caps["paypal_test_mode"] is False

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
        # The buyer still has a real way to pay.
        assert caps["methods"]["invoice"] is True

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
        anon, _ = api

        async def _boom(*args, **kwargs):
            raise pm.PaymentError(error)

        with _gateway_config(moyasar=MOYASAR_SECRET), _bank_file(iban="SA0380000000608010167519"):
            pm.initiate_moyasar = _boom
            r = await anon.post(
                "/api/payments",
                json={"package": "growth", "method": "mada", "customer_name": "مشتر"},
            )
        return r

    async def test_the_invoice_link_the_response_promises_actually_opens(self, api, monkeypatch):
        r = await self._post_card(api, "Moyasar error 401: Invalid authorization credentials")
        assert r.status_code == 200
        body = r.json()
        assert body["gateway"] == "invoice"
        invoice_url = body["invoice_url"]
        assert invoice_url == f"/invoice/{body['payment_id']}"

        anon, _ = api
        page = await anon.get(invoice_url)
        assert page.status_code == 200, f"dead invoice link: {invoice_url}"
        assert body["payment_id"] in page.text

    async def test_the_payment_is_reachable_after_the_gateway_failed(self, api, monkeypatch):
        r = await self._post_card(api, "Moyasar error 401: Invalid authorization credentials")
        payment_id = r.json()["payment_id"]
        anon, _ = api
        fetched = await anon.get(f"/api/payments/{payment_id}")
        assert fetched.status_code == 200

    async def test_the_buyer_can_report_the_transfer_on_that_invoice(self, api, monkeypatch):
        r = await self._post_card(api, "Moyasar error 401: Invalid authorization credentials")
        payment_id = r.json()["payment_id"]
        anon, _ = api
        report = await anon.post(f"/api/payments/{payment_id}/transfer-reported")
        assert report.status_code == 200

    async def test_the_gateway_error_is_not_shown_to_the_buyer(self, api, monkeypatch):
        r = await self._post_card(api, "Moyasar error 401: Invalid authorization credentials")
        assert "401" in r.json()["message"]  # the owner still sees the cause
        anon, _ = api
        page = await anon.get(r.json()["invoice_url"])
        assert "Moyasar error" not in page.text
        assert "Invalid authorization credentials" not in page.text


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
        assert "wa.me/966552978753" in body
        assert "t.me/AlNarjs7BOT" in body
        assert "DEADBEEF" in body.split("wa.me")[0] or "text=" in body

    async def test_a_malformed_reference_does_not_crash(self, api):
        anon, _ = api
        r = await anon.get("/invoice/not-a-uuid-at-all")
        assert r.status_code == 404
        assert "لم نتمكن" in r.text

    async def test_the_english_buyer_gets_the_english_page(self, api):
        anon, _ = api
        r = await anon.get("/invoice/deadbeef-0000-0000-0000-000000000000", cookies={"narjis_lang": "en"})
        assert "We could not load this invoice" in r.text
        assert "Send the reference on WhatsApp" in r.text

    async def test_a_real_invoice_is_never_replaced_by_the_recovery_page(self, api, maker):
        anon, _ = api
        payment = await _insert_payment(maker)
        r = await anon.get(f"/invoice/{payment.id}")
        assert r.status_code == 200
        assert "لم نتمكن من عرض هذه الفاتورة" not in r.text


# ---------------------------------------------------------------------------
# Transfer instructions
# ---------------------------------------------------------------------------


class TestTransferInstructions:
    def test_total_includes_vat_and_matches_the_invoice_maths(self):
        payment = Payment(id=uuid4(), amount=80000, currency="SAR", status="invoice")
        out = pm.transfer_instructions(payment)
        assert out["vat_halalas"] == pm.vat_amount(80000)
        assert out["total_halalas"] == pm.total_with_vat(80000)
        assert out["total_sar"] == round(pm.total_with_vat(80000) / 100, 2)

    def test_reference_is_the_eight_character_code_the_buyer_quotes(self):
        payment = Payment(id=uuid4(), amount=80000, currency="SAR", status="invoice")
        assert pm.transfer_instructions(payment)["reference"] == str(payment.id)[:8].upper()

    def test_whatsapp_link_carries_the_reference_and_the_amount(self):
        from urllib.parse import parse_qs, urlparse

        payment = Payment(id=uuid4(), amount=80000, currency="SAR", status="invoice")
        out = pm.transfer_instructions(payment)
        link = out["contact"]["whatsapp"]
        assert link.startswith("https://wa.me/966")
        text = parse_qs(urlparse(link).query).get("text", [""])[0]
        assert out["reference"] in text
        assert f"{out['total_sar']:.2f}" in text

    def test_bank_details_appear_only_when_the_owner_publishes_them(self):
        payment = Payment(id=uuid4(), amount=80000, currency="SAR", status="invoice")
        with _bank_file():
            assert pm.transfer_instructions(payment)["bank"] == {}
        with _bank_file(iban="SA0380000000608010167519", bank_name="مصرف الراجحي"):
            bank = pm.transfer_instructions(payment)["bank"]
        assert bank["iban"] == "SA0380000000608010167519"
        assert bank["bank_name"] == "مصرف الراجحي"


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

        r = await anon.post(f"/api/payments/{payment.id}/transfer-reported")
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

        await anon.post(f"/api/payments/{payment.id}/transfer-reported")
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

        await anon.post(f"/api/payments/{payment.id}/transfer-reported")
        second = await anon.post(f"/api/payments/{payment.id}/transfer-reported")
        assert second.status_code == 200
        assert second.json()["already_reported"] is True
        assert len(alerts) == 1

    async def test_a_failing_alert_keeps_the_record(self, api, maker, monkeypatch):
        anon, _ = api

        async def boom(text: str):
            raise RuntimeError("telegram is down")

        monkeypatch.setattr("src.services.telegram_sender.send_owner_alert", boom)
        payment = await _insert_payment(maker)

        r = await anon.post(f"/api/payments/{payment.id}/transfer-reported")
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

        r = await anon.post(f"/api/payments/{payment.id}/transfer-reported")
        assert r.status_code == 409

    async def test_an_already_paid_invoice_is_left_alone(self, api, maker, monkeypatch):
        anon, _ = api
        alerts: list[str] = []

        async def fake_alert(text: str):
            alerts.append(text)
            return {"ok": True}

        monkeypatch.setattr("src.services.telegram_sender.send_owner_alert", fake_alert)
        payment = await _insert_payment(maker, status="paid")

        r = await anon.post(f"/api/payments/{payment.id}/transfer-reported")
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
        r = await anon.post("/api/payments", json={"package": "platinum", "method": "invoice"})
        assert r.status_code == 400

    async def test_the_invoice_fallback_carries_the_amount_the_invoice_bills(self, api):
        anon, _ = api
        from src.services import catalog

        with _gateway_config():
            r = await anon.post(
                "/api/payments",
                json={"package": "growth", "method": "invoice", "customer_name": "-buy-test"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["gateway"] == "invoice"
        assert body["invoice_total"] == pm.total_with_vat(catalog.PACKAGES["growth"]["amount"])
        assert body["invoice_url"] == f"/invoice/{body['payment_id']}"

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
        assert "{% if not xfer.bank.iban and xfer.contact.whatsapp %}" in partial

    async def test_the_invoice_offers_whatsapp_when_no_bank_details_exist(self, api, maker):
        anon, _ = api
        payment = await _insert_payment(maker)
        with _bank_file():
            r = await anon.get(f"/invoice/{payment.id}")
        assert r.status_code == 200
        body = r.text
        assert "لم تُنشر بيانات الحساب بعد" in body
        assert "wa.me" in body
        assert "نسخ الآيبان" not in body

    async def test_the_invoice_publishes_the_iban_when_it_is_set(self, api, maker):
        anon, _ = api
        payment = await _insert_payment(maker)
        with _bank_file(iban="SA0380000000608010167519", bank_name="Al Rajhi"):
            r = await anon.get(f"/invoice/{payment.id}")
        body = r.text
        assert "SA0380000000608010167519" in body
        assert "لم تُنشر بيانات الحساب بعد" not in body
        assert "نسخ الآيبان" in body

    def test_the_checkout_asks_the_server_which_methods_are_real(self):
        portal = self._read("portal.html")
        assert "/api/payments/capabilities" in portal
        assert "cap.methods[x.m]" in portal

    def test_a_hidden_method_is_explained_rather_than_silently_dropped(self):
        portal = self._read("portal.html")
        assert "if (hidden) {" in portal
        assert "coCardNote" in portal

    def test_the_invoice_branch_leads_the_buyer_to_the_payable_invoice(self):
        portal = self._read("portal.html")
        assert "data.invoice_url || ('/invoice/' + data.payment_id)" in portal

    def test_checkout_fires_the_money_event_for_the_pixel(self):
        portal = self._read("portal.html")
        assert "fbq('track', 'InitiateCheckout'" in portal

    def test_the_confirmation_shows_sar_not_halalas(self):
        """/api/payments speaks halalas; 172500 printed as SAR reads as 172,500 SAR."""
        portal = self._read("portal.html")
        assert "data.total.toLocaleString()" not in portal
        assert "sar(due)" in portal

    def test_the_confirmation_quotes_the_same_number_the_invoice_bills(self):
        portal = self._read("portal.html")
        assert "data.invoice_total || data.total" in portal

    def test_the_purchase_event_reaches_the_ad_platform_in_sar(self):
        status = self._read("payment_status.html")
        assert "Number(st.value || st.total || st.amount || 0) / 100" in status
        assert "value: st.value || (st.total || st.amount || 0)" not in status

    def test_a_captured_lead_fires_the_lead_event(self):
        for name in ("early_access.html", "guide.html", "landing.html"):
            assert "fbq('track', 'Lead')" in self._read(name)


class TestTransferModule:
    def test_contact_channels_have_no_empty_whatsapp_link(self):
        channels = transfer.contact_channels()
        assert channels["telegram"].startswith("https://t.me/")
        assert channels["whatsapp"] == "" or channels["whatsapp"].startswith("https://wa.me/")

    def test_a_prefilled_message_is_url_encoded(self):
        link = transfer.contact_buttons("ABCD1234", 920.0, "مؤسسة")["whatsapp"]
        assert link.startswith("https://wa.me/966")
        assert " " not in link.split("?text=")[1]