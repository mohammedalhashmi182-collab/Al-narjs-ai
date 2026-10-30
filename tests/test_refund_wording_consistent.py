"""Public and prompt surfaces do not promise a refund outcome.

Refund questions go to AlNarjisai@gmail.com. The checkout consent uses that
wording and does not state an exception, a guarantee, or an always-refunded case.
"""

from pathlib import Path

import httpx

from src.core import karma_persona
from src.services import policies

AR = "لا نعد هنا بنتيجة استرداد. أسئلة الاسترداد تُراجع عبر البريد AlNarjisai@gmail.com."
EN = "We do not promise a refund outcome here. Refund questions are reviewed by email at AlNarjisai@gmail.com."

SURFACES = [
    "src/services/policies.py",
    "src/core/karma_persona.py",
    "data/kb/narjs_services.md",
    "src/web/templates/portal.html",
    "src/web/templates/terms.html",
    "src/web/templates/refund_policy.html",
    "src/web/templates/partials/_invoice_consent.html",
    "agents/base/customer_service.yaml",
    "agents/base/sales_closer.yaml",
]
PROMISES = (
    "نسترد رسوم الإعداد",
    "يُسترد دائماً",
    "غير قابل للاسترداد بعد التفعيل",
    "we refund the setup fee",
    "always refunded",
    "non-refundable after activation",
)


def test_consent_constants_promise_nothing():
    assert policies.REFUND_CONSENT_AR == AR
    assert policies.REFUND_CONSENT_EN == EN


def test_surfaces_use_the_neutral_sentence_and_drop_promises():
    bad = []
    for name in SURFACES:
        text = Path(name).read_text(encoding="utf-8")
        if AR not in text and EN not in text and "{{ refund_consent_ar }}" not in text:
            bad.append(f"{name}: missing the neutral sentence")
        low = text.lower()
        for phrase in PROMISES:
            if phrase.lower() in low:
                bad.append(f"{name}: still says {phrase}")
    assert not bad, bad


def test_assistant_prompt_and_policy_prompt_carry_the_rule():
    prompt = karma_persona.build_consult_system_prompt(
        locale="ar", packages_text="", employees_text=""
    )
    assert AR in prompt
    assert AR in policies.POLICY_PROMPT


async def _get(path):
    from src.main import app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", follow_redirects=True
    ) as c:
        r = await c.get(path)
    assert r.status_code == 200
    return r.text


async def test_portal_and_terms_agree_word_for_word():
    for lang, text in (("ar", AR), ("en", EN)):
        portal = await _get(f"/{lang}/portal")
        terms = await _get(f"/{lang}/terms")
        assert text in portal and text in terms
