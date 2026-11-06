"""Public consultant facts come from the catalog and do not self-identify as Grok."""

from src.ai.router import system_prompt
from src.core.karma_persona import build_consult_system_prompt
from src.services import catalog
from src.services.advisor_knowledge import site_system_addon, voice_facts
from src.services.rag import site_kb
from src.services.support import SUPPORT_EMAIL
from src.services.voice_live import session_instructions

_GROK_SELF = (
    "i am grok",
    "i'm grok",
    "أنا grok",
    "أنا جروك",
)


def _identity_does_not_claim_grok(text: str) -> None:
    lowered = text.lower()
    for phrase in _GROK_SELF:
        assert phrase not in lowered
    assert "مستشار النرجس" in text
    assert "grok" in lowered  # the prohibition names it; the persona does not adopt it


def test_voice_and_site_instructions_share_catalog_facts():
    voice = session_instructions()
    site = system_prompt()
    kb = " ".join(body for _, body in site_kb.docs())
    consult = build_consult_system_prompt(locale="ar", packages_text="P", employees_text="E")
    billed = catalog.BILLING_PERIODS["annual"]["months_billed"]
    granted = catalog.BILLING_PERIODS["annual"]["months_granted"]

    for text in (voice, site, kb, consult, voice_facts(), site_system_addon()):
        _identity_does_not_claim_grok(text)
        assert "karmaai.online" in text
        assert SUPPORT_EMAIL in text
        assert str(billed) in text and str(granted) in text
        assert "bank transfer" in text.lower() or "تحويل بنكي" in text
    for text in (voice, site, kb, voice_facts(), site_system_addon()):
        for key in catalog.PACKAGE_ORDER:
            plan = catalog.PACKAGES[key]
            assert plan["name"] in text
            assert f"{int(plan['price']):,}" in text
            assert f"{int(plan['limits']['conversations']):,}" in text
            setup = int(plan.get("setup_fee") or 0) // 100
            if setup == 0:
                assert "no setup fee" in text.lower() or "بدون رسوم إعداد" in text
            else:
                assert f"{setup:,}" in text
    assert "Enterprise" in voice  # catalog name_en for the 2,990 plan
    assert catalog.PACKAGES["sharikat"]["name_en"] in voice
    assert "not physical products" in voice
    assert "مو منتجات" in site
    assert "owner will follow up" in voice.lower()
    assert "المالك بيتابع" in site
    assert "does not issue tax invoices" in voice or "do not issue tax invoices" in voice
    assert "فواتير ضريبية" in site
    assert "delivery time depends on the scope" in voice.lower()
    assert "لا توعد بمدة ثابتة" in site
    assert "NEVER say you are Grok" in voice
    assert "لا تقل إنك Grok" in site
