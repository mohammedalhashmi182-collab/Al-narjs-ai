"""One extra-agent price everywhere (lesson 3 + extra-agent fix).

Canonical: catalog.ADDON_AGENT["amount"] = 299 SAR/month pre-VAT, max 12,
VAT 15% on top. Every surface must render that same number; the in-plan
"average per agent" figure may never show more than it (599/2 = 299.5 used
to round UP to 300 in the pricing table).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.services import catalog, payments, smart_reply, social_agent, zatca

ROOT = Path(__file__).resolve().parents[1]
PRICE = catalog.ADDON_AGENT["amount"] // 100


@pytest.fixture(scope="module")
def pages() -> dict[str, str]:
    from src.main import app

    with TestClient(app) as c:
        out = {lang: c.get(f"/{lang}/home") for lang in ("ar", "en")}
    assert all(r.status_code == 200 for r in out.values())
    return {k: r.text for k, r in out.items()}


def test_canonical_config() -> None:
    assert catalog.ADDON_AGENT["amount"] == 29900
    assert catalog.ADDON_AGENT["price"] == "299" == str(PRICE)
    assert catalog.MAX_ADDON_AGENTS == 12
    assert catalog.with_vat(29900) == 34385          # 343.85 SAR incl. 15% VAT


def test_plan_math_uses_the_addon_price() -> None:
    for key in catalog.PACKAGE_ORDER:
        base = catalog.plan_amount(key, "monthly", 0)
        for n in (1, 2, catalog.MAX_ADDON_AGENTS):
            assert catalog.plan_amount(key, "monthly", n) - base == n * 29900
        assert catalog.plan_amount(key, "annual", 1) - catalog.plan_amount(key, "annual", 0) == 29900 * 10


def test_in_plan_average_never_exceeds_extra_agent_price() -> None:
    for key in catalog.PACKAGE_ORDER:
        pkg = catalog.PACKAGES[key]
        avg = int(pkg["per_agent_price"])
        assert avg == pkg["amount"] // pkg["agents"] // 100   # rounded down, one formula
        assert avg <= PRICE, (key, avg)


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_landing_renders_only_the_canonical_price(pages: dict[str, str], lang: str) -> None:
    page = pages[lang]
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page))
    if lang == "ar":
        assert f"وكيل إضافي بـ{PRICE} ر.س" in text
        assert "سعر الوكيل الواحد" not in text          # ambiguous label removed
        found = re.findall(r"وكيل إضافي[^0-9]{0,12}(\d{3})", text)
    else:
        assert f"An extra agent is SAR {PRICE}" in text
        found = re.findall(r"[Ee]xtra agents?[^0-9]{0,20}(\d{3})", text)
    assert found and set(found) == {str(PRICE)}, found
    # comparison-table row: "+299" once per public plan
    assert page.count(f"+{PRICE}</span>") == len(catalog.PACKAGE_ORDER)
    # average row: values come from the one helper and none exceeds the add-on
    for key in catalog.PACKAGE_ORDER:
        assert int(catalog.PACKAGES[key]["per_agent_price"]) <= PRICE
    assert ">300<" not in page


def test_json_ld_states_the_canonical_price(pages: dict[str, str]) -> None:
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', pages["en"], re.S)
    blob = json.dumps([json.loads(b) for b in blocks], ensure_ascii=False)
    assert f"Extra agents: SAR {PRICE} per agent" in blob
    assert not re.search(r"Extra agents?: SAR (?!%d\b)\d+" % PRICE, blob)


def test_bots_checkout_and_invoice_agree() -> None:
    assert f"وكيل إضافي بـ {PRICE} ريال" in smart_reply.plan_lines("radd")
    assert f"بـ {PRICE} ريال" in social_agent.compose_post("addon")
    pay = SimpleNamespace(package="bay", billing_period="monthly", addon_agents=3,
                          addon_conversation_packs=0, addon_voice_packs=0, is_renewal=False,
                          founding=False, description="", amount=payments.package_amount("bay", "monthly", 3)
                          + catalog.setup_fee("bay", "monthly"))
    lines = zatca.build_lines(pay)
    addon = [l for l in lines if catalog.ADDON_AGENT["name"] in l["name"]]
    assert addon and addon[0]["qty"] == 3 and addon[0]["unit"] == 29900
    assert not any("تسوية" in l["name"] or "خصم" in l["name"] for l in lines)


def test_no_hard_coded_extra_agent_price_anywhere() -> None:
    """Any file that quotes an extra-agent price must quote the canonical one."""
    legacy = str(catalog.LEGACY_ADDON_AMOUNT // 100)   # grandfathered subscribers only
    pat = re.compile(r"(وكيل إضافي|الوكيل الإضافي|extra agents?|add-on agents?)[^0-9\n]{0,25}(\d{3})", re.I)
    globs = ["src/web/templates/**/*.html", "knowledge/**/*.json", "kb/**/*", "docs/**/*.md", "src/services/*.py"]
    bad = []
    for g in globs:
        for f in ROOT.glob(g):
            if f.is_file():
                for m in pat.finditer(f.read_text(encoding="utf-8", errors="ignore")):
                    ok = {str(PRICE), "000"} | ({legacy} if "original" in m.group(0) else set())
                    if m.group(2) not in ok:
                        bad.append(f"{f.relative_to(ROOT)}: {m.group(0)}")
    assert not bad, bad
