"""Owner decision 24 Oct 2026: the only refund after activation is the setup fee
(agent not working within 10 business days). Every public or prompt surface must
say so; none may state 'non-refundable after activation' without the exception."""

import re
from pathlib import Path

import httpx

from src.core import karma_persona
from src.services import policies

AR = (
    "الخدمة تبدأ بعد تفعيلها والمبلغ غير قابل للاسترداد بعد التفعيل، باستثناء رسوم الإعداد: "
    "إن لم يعمل الوكيل خلال 10 أيام عمل نسترد رسوم الإعداد فقط"
)
EN = (
    "The service starts once it is activated and the amount is non-refundable after activation, "
    "except the setup fee: if the agent is not working within 10 business days, we refund the setup fee only"
)

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
CONTRADICT = [
    (re.compile(r"غير قابل للاسترداد بعد التفعيل"), "رسوم الإعداد"),
    (re.compile(r"non-refundable after activation", re.I), "setup fee"),
    (re.compile(r"لا (?:يوجد )?استرداد بعد (?:تفعيل الخدمة|التفعيل)"), "رسوم الإعداد"),
    (re.compile(r"no refunds? after activation|refunds: none after activation", re.I), "setup fee"),
]
NOW = re.compile(r"تبدأ فوراً|starts immediately|فور استلام الدفعة|as soon as payment")


def test_consent_constants_are_the_owner_text():
    assert policies.REFUND_CONSENT_AR == AR
    assert policies.REFUND_CONSENT_EN == EN


def test_no_surface_states_no_refund_without_the_setup_fee_exception():
    bad = []
    for f in SURFACES:
        for n, line in enumerate(Path(f).read_text(encoding="utf-8").splitlines(), 1):
            for pat, needed in CONTRADICT:
                if pat.search(line) and needed not in line.lower() and needed not in line:
                    bad.append(f"{f}:{n}")
            if NOW.search(line):
                bad.append(f"{f}:{n} (immediately)")
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
        assert text in portal and text in terms, lang
        assert not NOW.search(portal) and not NOW.search(terms)
