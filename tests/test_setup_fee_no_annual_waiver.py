"""Owner decision 24 Oct 2026: setup fees 0 / 990 / 1,990 are charged on monthly
AND annual billing; annual = pay 10 months, get 12; no annual setup-fee waiver."""
import re
from pathlib import Path

import pytest

from src.services import catalog
from src.services import payments as pm

ROOT = Path(__file__).resolve().parents[1]
SCANNED = [
    "src/services/catalog.py", "src/services/payments.py", "src/services/rag/site_kb.py",
    "src/services/policies.py", "src/main.py", "data/kb/narjs_services.md",
    "src/web/templates/partials/_pricing_section.html", "src/web/templates/portal.html",
    "src/web/templates/terms.html", "src/web/templates/refund_policy.html",
]
WAIVER = re.compile(
    r"waived on annual|waived for annual|waiv\w* (?:on|for) annual|annual[^.\n]{0,40}waiv"
    r"|تُعفى في الاشتراك السنوي|تُلغى مع (?:الاشتراك )?السنوي|رسوم الإعداد معفاة|معفاة مع السنوي",
    re.IGNORECASE,
)


@pytest.mark.parametrize("rel", SCANNED)
def test_no_annual_setup_fee_waiver_text(rel):
    hits = WAIVER.findall((ROOT / rel).read_text(encoding="utf-8"))
    assert not hits, f"{rel}: annual setup-fee waiver text still present: {hits}"


def test_site_kb_and_catalog_scope_have_no_waiver():
    from src.services.rag import site_kb

    blob = " ".join(t for _, t in site_kb.docs())
    blob += " ".join(" ".join(p.get("scope_en") or []) + " ".join(p.get("scope") or []) for p in catalog.PACKAGES.values())
    assert not WAIVER.search(blob)


@pytest.mark.parametrize("key,fee", [("bidaya", 0), ("numuw", 99000), ("sharikat", 199000)])
def test_setup_fee_same_on_monthly_and_annual(key, fee):
    assert catalog.PACKAGES[key]["setup_fee"] == fee
    assert catalog.setup_fee(key, "monthly") == fee
    assert catalog.setup_fee(key, "annual") == fee
    assert pm.setup_fee_amount(key, "annual") == fee


@pytest.mark.parametrize("key", list(catalog.PACKAGE_ORDER))
def test_annual_total_is_ten_months_plus_setup_fee(key):
    pkg = catalog.PACKAGES[key]
    assert catalog.BILLING_PERIODS["annual"]["months_billed"] == 10
    assert catalog.BILLING_PERIODS["annual"]["months_granted"] == 12
    total = catalog.plan_amount(key, "annual") + catalog.setup_fee(key, "annual")
    assert total == pkg["amount"] * 10 + pkg["setup_fee"]


def test_monthly_prices_unchanged():
    assert [catalog.PACKAGES[k]["amount"] for k in catalog.PACKAGE_ORDER] == [79000, 149000, 299000]


def test_ecommerce_tagline_copy_fixed():
    src = (ROOT / "src/services/catalog.py").read_text(encoding="utf-8")
    assert "الزيارة السلة" not in src
    assert "يرفع التحويل من الزيارة إلى السلة إلى الطلب" in src
