"""Salla/Zid store connection is «قريباً» / coming soon everywhere.

The integration code exists, but both partner apps are still private drafts and
no merchant store has been connected, so no surface may sell it as available or
"on request" (owner rule: never claim available based only on code existing).
"""

import re
from pathlib import Path

from src.services import catalog, draft_qa, policies

ROOT = Path(__file__).resolve().parents[1]

_AVAILABLE = re.compile(r"on request|available|متاح|عند الطلب|نُعدّه لك|set up by us", re.I)
_SOON = re.compile(r"قريباً|coming soon", re.I)


def _sources() -> dict[str, str]:
    out = {
        "POLICY_PROMPT": policies.POLICY_PROMPT,
        "OWNER_FAQ_AR": policies.OWNER_FAQ_AR,
        "karma_persona": (ROOT / "src/core/karma_persona.py").read_text(encoding="utf-8"),
        "kb": (ROOT / "data/kb/narjs_services.md").read_text(encoding="utf-8"),
        "guide": (ROOT / "src/web/templates/guide.html").read_text(encoding="utf-8"),
    }
    for name in ("customer_service.yaml", "sales_closer.yaml"):
        out[name] = (ROOT / "agents" / "base" / name).read_text(encoding="utf-8")
    return out


def _store_sentences(text: str):
    text = re.sub(r"\n  +(?=[a-z(])", " ", text)  # re-join wrapped prose lines
    for ln in text.splitlines():
        for sent in re.split(r"(?<=[.؛;])\s+|(?<=\.\))\s*", ln):
            if re.search(r"سلة|زد|Salla|Zid", sent) and re.search(r"ربط|connect", sent, re.I):
                yield sent


def test_every_store_connection_mention_says_coming_soon():
    seen = 0
    for name, text in _sources().items():
        for sent in _store_sentences(text):
            seen += 1
            assert _SOON.search(sent), (name, sent[:140])
    assert seen >= 7


def test_no_surface_sells_it_as_available_or_on_request():
    for name, text in _sources().items():
        for sent in _store_sentences(text):
            core = re.sub(r"never say it is available|لا تقل إنه متاح", "", sent, flags=re.I)
            assert not _AVAILABLE.search(core), (name, sent[:140])


def test_policy_and_faq_wording():
    assert "Salla/Zid store connection is coming soon" in policies.POLICY_PROMPT
    assert "ربط سلة أو زد «قريباً»" in policies.OWNER_FAQ_AR


def test_catalog_lists_it_under_coming_only():
    g = catalog.PACKAGES["numuw"]
    assert g["coming"] == ["ربط سلة أو زد (قريباً)"]
    assert any("coming soon" in s.lower() and "Salla" in s for s in g["coming_en"])
    assert not any("سلة" in s for s in g["scope"]) and not any("Salla" in s for s in g["scope_en"])


def test_terms_and_refund_list_it_as_coming():
    for page in ("terms.html", "refund_policy.html"):
        html = (ROOT / "src/web/templates" / page).read_text(encoding="utf-8")
        assert "الوكيل الصوتي وربط سلة أو زد" in html, page
    refund = (ROOT / "src/web/templates/refund_policy.html").read_text(encoding="utf-8")
    assert "the voice agent and the Salla or Zid connection" in refund


def test_draft_qa_flags_live_store_claims_but_allows_coming_soon():
    for s in ("ربط متجرك على سلة متاح الآن", "Salla integration is included in your plan"):
        codes = [i["code"] for i in draft_qa.score_draft(s)["issues"]]
        assert "unbuilt_feature" in codes, s
    ok = "ربط سلة أو زد قريباً وغير مشمول حالياً."
    assert not any(i["code"] == "unbuilt_feature" for i in draft_qa.score_draft(ok)["issues"])


def test_draft_qa_still_flags_write_or_self_serve_claims():
    for s in ("الوكيل على سلة يعدل المنتجات بنفسه", "Salla installs itself automatically"):
        assert any(i["code"] == "store_write_claim" for i in draft_qa.score_draft(s)["issues"]), s
