"""Salla/Zid: available on request, set up by Al-Narjs, read-only. Never «قريباً», never write access."""

import re
from pathlib import Path

from src.services import catalog, draft_qa, policies

ROOT = Path(__file__).resolve().parents[1]

AR_HONEST = "ربط متجر سلة أو زد متاح عند الطلب"
EN_HONEST = "Salla/Zid store connection is available on request"

# Claims that would be untrue: write access, self-serve install, managing the store.
FORBIDDEN = [
    re.compile(r"\b(?:write access|can (?:edit|update|create|delete|manage))\b", re.I),
    re.compile(
        r"self-serve|one-click|installs? (?:itself|automatically)|connect it yourself", re.I
    ),
    re.compile(
        r"صلاحية\s+(?:كتابة|تعديل)|يعدّ?ل\s+(?:المنتجات|الطلبات|الأسعار)|يدير\s+(?:المنتجات|الطلبات)|تربطه\s+بنفسك"
    ),
]
# Sentences that deny a capability ("no write access", "never say ...") are allowed.
_NEGATION = re.compile(r"\bno\b|\bnever\b|\bnot\b|بدون|دون|لا\s|ما\s", re.I)


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


def _store_lines(text: str) -> list[str]:
    return [
        ln
        for ln in text.splitlines()
        if re.search(r"سلة|زد\b|Salla|Zid", ln) and re.search(r"ربط|connect", ln, re.I)
    ]


def test_no_coming_soon_wording_for_salla_zid():
    for name, text in _sources().items():
        for ln in _store_lines(text):
            assert "قريب" not in ln and "coming soon" not in ln.lower(), (name, ln[:120])
            assert "غير مشمول" not in ln and "not included" not in ln.lower(), (name, ln[:120])


def test_honest_wording_present_everywhere():
    assert EN_HONEST in policies.POLICY_PROMPT and "no write access" in policies.POLICY_PROMPT
    assert AR_HONEST in policies.OWNER_FAQ_AR and "قراءة فقط" in policies.OWNER_FAQ_AR
    for name in ("customer_service.yaml", "sales_closer.yaml"):
        text = (ROOT / "agents" / "base" / name).read_text(encoding="utf-8")
        assert EN_HONEST in text and "read-only" in text and "no write access" in text
    kb = (ROOT / "data/kb/narjs_services.md").read_text(encoding="utf-8")
    assert kb.count(AR_HONEST) >= 2 and "بدون أي صلاحية كتابة" in kb
    assert (
        "read-only" in _sources()["karma_persona"]
        and "no write access" in _sources()["karma_persona"]
    )


def test_no_false_capability_claims():
    for name, text in _sources().items():
        for ln in _store_lines(text):
            for sent in re.split(r"(?<=[.؛:;])\s+|،\s*(?=و?بدون)", ln):
                if _NEGATION.search(sent):
                    continue
                for pat in FORBIDDEN:
                    m = pat.search(sent)
                    assert not m, (name, m.group(0) if m else "")


def test_catalog_lists_connection_as_available_on_request():
    g = catalog.PACKAGES["numuw"]
    ar = [s for s in g["scope"] if "سلة" in s]
    en = [s for s in g["scope_en"] if "Salla" in s]
    assert ar == ["ربط متجر سلة أو زد عند الطلب (قراءة فقط، نُعدّه لك)"]
    assert en == ["Salla or Zid store connection on request (read-only, set up by us)"]
    assert not any("سلة" in s for s in g["coming"]) and not any(
        "Salla" in s for s in g["coming_en"]
    )


def test_draft_qa_flags_write_or_self_serve_claims():
    bad = [
        "الوكيل على سلة يعدل المنتجات بنفسه",
        "The Zid connection can manage orders for you",
        "Salla installs itself automatically",
    ]
    for s in bad:
        assert any(i["code"] == "store_write_claim" for i in draft_qa.score_draft(s)["issues"]), s
    ok = "ربط متجر سلة متاح عند الطلب بصلاحية قراءة فقط، نُعدّه لك."
    assert not any(
        i["code"] in ("store_write_claim", "unbuilt_feature")
        for i in draft_qa.score_draft(ok)["issues"]
    )
