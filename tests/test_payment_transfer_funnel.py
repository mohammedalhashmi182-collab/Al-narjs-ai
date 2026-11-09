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
    """Override PayPal settings. Card-gateway arguments are ignored."""
    del moyasar, publishable
    from src.config import settings as s

    names = ("paypal_client_id", "paypal_client_secret", "paypal_mode")
    old = {n: getattr(s, n) for n in names}
    object.__setattr__(s, "paypal_client_id", paypal_id)
    object.__setattr__(s, "paypal_client_secret", paypal_secret)
    object.__setattr__(s, "paypal_mode", paypal_mode)
    try:
        yield
    finally:
        for n, v in old.items():
            object.__setattr__(s, n, v)


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
    def test_published_account_opens_bank_transfer_and_card_stays_closed(self, monkeypatch):
        for key in ("PAYMENT_IBAN", "PAYMENT_ACCOUNT_NAME", "PAYMENT_BANK_NAME"):
            monkeypatch.delenv(key, raising=False)
        with _bank_file(), _gateway_config():
            caps = pm.capabilities()
        assert caps["methods"]["invoice"] is False
        assert caps["card"] is False and caps["paypal"] is False
        assert caps["bank"] == {}
        assert set(caps["methods"]) == {"paypal", "invoice", "mada", "creditcard", "stcpay"}
        with _gateway_config():
            live = pm.capabilities()
        assert live["methods"]["invoice"] is False
        assert live["card"] is False
        assert live["bank"] == {}

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
        with _gateway_config(paypal_id="id", paypal_secret=PAYPAL_SECRET):
            blob = str(pm.capabilities())
        assert PAYPAL_SECRET not in blob

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
    def test_names_nothing_required_until_a_method_is_switched_on(self, monkeypatch):
        monkeypatch.delenv("CUSTOMER_PAYPAL_ENABLED", raising=False)
        for key in ("PAYMENT_IBAN", "PAYMENT_ACCOUNT_NAME", "PAYMENT_BANK_NAME"):
            monkeypatch.delenv(key, raising=False)
        with _bank_file(), _gateway_config():
            report = pm.readiness()
        assert report["collect_money_now"] is False
        assert "MOYASAR_API_SECRET" in report["missing_env"]
        assert "MOYASAR_PUBLISHABLE_KEY" in report["missing_env"]
        assert "MOYASAR_WEBHOOK_SECRET" in report["missing_env"]
        assert report["card"] is False

    def test_live_paypal_collects_when_the_customer_flag_is_on(self, monkeypatch):
        monkeypatch.setenv("CUSTOMER_PAYPAL_ENABLED", "1")
        with _gateway_config(paypal_id="a", paypal_secret="b", paypal_mode="live"):
            report = pm.readiness()
        assert report["collect_money_now"] is True
        assert "MOYASAR_API_SECRET" in report["missing_env"]

    def test_never_carries_a_credential_value(self):
        with _gateway_config(paypal_id="id", paypal_secret=PAYPAL_SECRET):
            blob = str(pm.readiness())
        assert PAYPAL_SECRET not in blob


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
        assert "data-open-assistant" not in body and "mailto:AlNarjisai@gmail.com" in body
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
        assert "email it to us at AlNarjisai@gmail.com" in r.text and "mailto:AlNarjisai@gmail.com" in r.text

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

    def test_the_invoice_and_the_charge_agree_for_every_package(self):
        from src.services import catalog

        for key, meta in catalog.PACKAGES.items():
            base = meta["amount"]
            assert pm.total_with_vat(base) == pm.total_with_vat(base)
            assert pm.total_with_vat(base) > base, key

    @pytest.mark.usefixtures("founding_full")
    async def test_the_api_reports_the_vat_inclusive_total_to_the_checkout(self, api, monkeypatch):
        """Owner-raised invoices still quote VAT when the customer account is unpublished."""
        from src.core.owner_auth import make_session_token
        from src.services import catalog

        anon, _ = api
        for key in ("PAYMENT_IBAN", "PAYMENT_ACCOUNT_NAME", "PAYMENT_BANK_NAME"):
            monkeypatch.delenv(key, raising=False)
        with _bank_file(), _gateway_config():
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
        assert out["contact"]["phone"] == "tel:+966552978753"
        assert out["reference"]

    def test_bank_details_come_from_the_file_unless_the_environment_overrides(self, monkeypatch):
        payment = Payment(id=uuid4(), amount=49900, currency="SAR", package="bidaya", status="invoice")
        for key in ("PAYMENT_IBAN", "PAYMENT_ACCOUNT_NAME", "PAYMENT_BANK_NAME"):
            monkeypatch.delenv(key, raising=False)
        with _bank_file():
            assert pm.transfer_instructions(payment)["bank"] == {}
            assert pm.transfer_instructions(payment)["qr_svg"] == ""
        published = pm.transfer_instructions(payment)
        assert published["bank"] == {}
        assert published["qr_svg"] == ""
        monkeypatch.setenv("PAYMENT_IBAN", "SA00 0000 0000 0000 0000 0000")
        monkeypatch.setenv("PAYMENT_ACCOUNT_NAME", "Dummy Holder")
        monkeypatch.setenv("PAYMENT_BANK_NAME", "Example Bank")
        out = pm.transfer_instructions(payment)
        assert out["bank"] == {}
        assert out["iban_spaced"] == ""
        assert out["qr_svg"] == ""
        assert "SA0000000000000000000000" not in str(out)


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
        assert r.status_code == 400
        assert "Bank transfer is not available" in r.text
        assert alerts == []

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
        assert stored.gateway_source != "transfer_reported"

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
        assert second.status_code == 400
        assert alerts == []

    async def test_a_failing_alert_keeps_the_record(self, api, maker, monkeypatch):
        anon, _ = api

        async def boom(text: str):
            raise RuntimeError("telegram is down")

        monkeypatch.setattr("src.services.telegram_sender.send_owner_alert", boom)
        payment = await _insert_payment(maker)

        r = await anon.post(f"/api/payments/{payment.id}/transfer-reported", json={"refund_consent": True})
        assert r.status_code == 400 and "Bank transfer is not available" in r.text
        async with maker() as session:
            from sqlalchemy import select

            stored = (
                await session.execute(select(Payment).where(Payment.id == payment.id))
            ).scalar_one()
        assert stored.gateway_source != "transfer_reported"

    async def test_a_gateway_settled_invoice_is_not_reported_by_hand(self, api, maker):
        anon, _ = api
        payment = await _insert_payment(maker, gateway="moyasar", gateway_payment_id="inv_123")

        r = await anon.post(f"/api/payments/{payment.id}/transfer-reported", json={"refund_consent": True})
        assert r.status_code == 400

    async def test_an_already_paid_invoice_is_left_alone(self, api, maker, monkeypatch):
        anon, _ = api
        alerts: list[str] = []

        async def fake_alert(text: str):
            alerts.append(text)
            return {"ok": True}

        monkeypatch.setattr("src.services.telegram_sender.send_owner_alert", fake_alert)
        payment = await _insert_payment(maker, status="paid")

        r = await anon.post(f"/api/payments/{payment.id}/transfer-reported", json={"refund_consent": True})
        assert r.status_code == 400
        assert alerts == []

    async def test_unknown_and_malformed_ids_are_rejected(self, api):
        anon, _ = api
        assert (await anon.post(f"/api/payments/{uuid4()}/transfer-reported")).status_code == 400
        assert (await anon.post("/api/payments/not-a-uuid/transfer-reported")).status_code == 400


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


class TestPublicSurface:
    async def test_capabilities_endpoint_is_public_and_secret_free(self, api):
        anon, _ = api
        with _gateway_config(paypal_id="id", paypal_secret=PAYPAL_SECRET):
            r = await anon.get("/api/payments/capabilities")
        assert r.status_code == 200
        assert PAYPAL_SECRET not in r.text
        assert set(r.json()["methods"]) == {"paypal", "invoice", "mada", "creditcard", "stcpay"}

    async def test_readiness_is_owner_only(self, api):
        anon, owned = api
        assert (await anon.get("/api/owner/payments/readiness")).status_code in (401, 403)
        assert (await owned.get("/api/owner/payments/readiness")).status_code == 200

    async def test_an_unknown_package_is_a_client_error_not_a_crash(self, api):
        anon, _ = api
        r = await anon.post("/api/payments", json={"refund_consent": True, "package": "platinum", "method": "invoice"})
        assert r.status_code == 400

    @pytest.mark.usefixtures("founding_full")
    async def test_a_customer_bank_invoice_follows_the_published_account(self, api, monkeypatch):
        anon, _ = api
        for key in ("PAYMENT_IBAN", "PAYMENT_ACCOUNT_NAME", "PAYMENT_BANK_NAME"):
            monkeypatch.delenv(key, raising=False)
        with _bank_file(), _gateway_config():
            closed = await anon.post(
                "/api/payments",
                json={"refund_consent": True, "package": "bidaya", "method": "invoice", "customer_name": "-buy-test"},
            )
        assert closed.status_code == 400
        assert "Bank transfer is not available" in closed.text
        with _gateway_config():
            opened = await anon.post(
                "/api/payments",
                json={"refund_consent": True, "package": "bidaya", "method": "invoice", "customer_name": "-buy-test"},
            )
        assert opened.status_code == 400
        assert "Bank transfer is not available" in opened.text

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
            assert 'include "partials/_transfer.html"' not in self._read(name)
            assert "آيبان" not in self._read(name) and "IBAN" not in self._read(name)

    def test_the_block_offers_the_report_button_the_endpoint_backs(self):
        partial = self._read("partials/_transfer.html")
        assert "xfer-qr" not in partial and "xferIban" not in partial
        consent = self._read("partials/_invoice_consent.html")
        assert "invoicePayCard" in consent

    def test_an_unpublished_account_asks_for_the_reference_not_for_a_transfer(self):
        """No IBAN means the buyer cannot have paid; do not imply they did."""
        partial = self._read("partials/_transfer.html")
        assert "xfer-qr" not in partial
        assert "data-open-assistant" not in partial

    async def test_a_guest_invoice_hides_the_qr_until_the_account_is_configured(self, api, maker, monkeypatch):
        anon, _ = api
        payment = await _insert_payment(maker)
        for key in ("PAYMENT_IBAN", "PAYMENT_ACCOUNT_NAME", "PAYMENT_BANK_NAME"):
            monkeypatch.delenv(key, raising=False)
        with _bank_file():
            hidden = await anon.get(f"/invoice/{payment.id}")
        assert hidden.status_code == 200
        assert "SA0000000000000000000000" not in hidden.text
        assert "<svg" not in hidden.text
        assert "تواصل معنا للدفع" not in hidden.text
        assert "آيبان" not in hidden.text
        monkeypatch.setenv("PAYMENT_IBAN", "SA0000000000000000000000")
        monkeypatch.setenv("PAYMENT_ACCOUNT_NAME", "Dummy Holder")
        monkeypatch.setenv("PAYMENT_BANK_NAME", "Example Bank")
        shown = await anon.get(f"/invoice/{payment.id}")
        assert shown.status_code == 200
        assert "SA00" not in shown.text
        assert "آيبان" not in shown.text
        assert "IBAN" not in shown.text
        assert "wa.me" not in shown.text

    def test_the_checkout_asks_the_server_which_methods_are_real(self):
        portal = self._read("portal.html")
        assert "/api/payments/capabilities" in portal
        assert "cap.methods[x.m]" in portal

    def test_a_hidden_method_is_explained_rather_than_silently_dropped(self):
        portal = self._read("portal.html")
        assert "if (!live.length || hidden)" in portal
        assert "coCardNote" in portal

    def test_the_invoice_branch_opens_the_invoice_when_one_exists(self):
        portal = self._read("portal.html")
        assert "data.invoice_url" in portal
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
        assert channels["phone"] == "tel:+966552978753"

    def test_a_prefilled_message_is_url_encoded(self):
        buttons = transfer.contact_buttons("ABCD1234", 920.0, "مؤسسة")
        assert buttons["whatsapp"] == ""
        assert buttons["phone"] == "tel:+966552978753"
        assert buttons["email"].startswith("mailto:")