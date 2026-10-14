"""PDPL: PII is masked before prompts reach external LLM providers."""
from __future__ import annotations

import pytest

from src.core import pii_mask
from src.core.model_provider import ModelProvider, ModelProviderType, ModelRequest, ModelResponse


@pytest.mark.parametrize("raw,kind", [
    ("راسلني على ali.s@example.com", "EMAIL"),
    ("جوالي 0551234567", "PHONE"),
    ("رقمي +966 55 123 4567", "PHONE"),
    ("رقمي 966551234567", "PHONE"),
    ("جوالي ٠٥٥١٢٣٤٥٦٧", "PHONE"),
    ("call +44 20 7946 0958", "PHONE"),
    ("هويتي 1012345678", "NATIONAL_ID"),
    ("إقامتي 2123456789", "NATIONAL_ID"),
    ("الآيبان SA0380000000608010167519", "IBAN"),
])
def test_masks_each_kind(raw, kind):
    masked, mapping = pii_mask.mask(raw)
    assert f"[{kind}_1]" in masked and list(mapping.values())[0] in raw
    assert pii_mask.unmask(masked, mapping) == raw


def test_leaves_prices_dates_and_order_numbers():
    text = "باقة بيع بـ 1,499 ريال، الطلب رقم 48213، الموعد 2026-10-14 الساعة 10"
    assert pii_mask.mask(text)[0] == text


def test_same_value_same_placeholder_across_fields():
    m: dict = {}
    a, m = pii_mask.mask("0551234567", m)
    b, m = pii_mask.mask("اتصل 0551234567 أو 0569999999", m)
    assert a == "[PHONE_1]" and b == "اتصل [PHONE_1] أو [PHONE_2]"


def test_switch_and_opt_out(monkeypatch):
    monkeypatch.delenv("PII_MASKING", raising=False)
    assert pii_mask.should_mask("gemini", {})
    assert not pii_mask.should_mask("ollama", {})
    assert not pii_mask.should_mask("gemini", {"pii_mask": False})
    monkeypatch.setenv("PII_MASKING", "off")
    assert not pii_mask.should_mask("gemini", {})


class _Spy:
    def __init__(self):
        self.seen = []

    async def complete(self, request):
        self.seen.append((request.prompt, request.system_prompt))
        return ModelResponse(content="سنتواصل على [PHONE_1] و [EMAIL_1]")


async def test_provider_never_sees_pii_and_reply_is_restored(monkeypatch):
    monkeypatch.delenv("PII_MASKING", raising=False)
    mp = ModelProvider.__new__(ModelProvider)
    spy = _Spy()
    mp._clients = {ModelProviderType.GEMINI: spy}
    req = ModelRequest(prompt="أنا سارة 0551234567 sara@example.com", system_prompt="العميل 1012345678")
    resp = await mp.complete("gemini:test", req)
    sent_prompt, sent_system = spy.seen[0]
    for secret in ("0551234567", "sara@example.com", "1012345678"):
        assert secret not in sent_prompt + sent_system
    assert resp.content == "سنتواصل على 0551234567 و sara@example.com"
    assert req.prompt.endswith("sara@example.com")  # caller's request restored
    assert req.metadata["pii_masked"] == ["EMAIL", "NATIONAL_ID", "PHONE"]


async def test_disabled_flag_sends_raw(monkeypatch):
    monkeypatch.setenv("PII_MASKING", "off")
    mp = ModelProvider.__new__(ModelProvider)
    spy = _Spy()
    mp._clients = {ModelProviderType.GEMINI: spy}
    await mp.complete("gemini:test", ModelRequest(prompt="0551234567"))
    assert spy.seen[0][0] == "0551234567"


def test_policy_pages_carry_cross_border_clause():
    from pathlib import Path

    tpl = Path(__file__).resolve().parent.parent / "src" / "web" / "templates"
    for name in ("privacy.html", "dpa.html", "subprocessors.html"):
        html = (tpl / name).read_text(encoding="utf-8")
        assert "نقل البيانات خارج المملكة" in html and "Transfers outside the Kingdom" in html, name
    doc = (tpl.parent.parent.parent / "docs" / "pdpl-transfer-risk-assessment.md").read_text(encoding="utf-8")
    for vendor in ("Gemini", "Moonshot", "Render", "Brevo", "PayPal", "Meta"):
        assert vendor in doc
