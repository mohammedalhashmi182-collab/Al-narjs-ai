from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANNED = ("فوري", "فوراً", "على مدار الساعة")


def _line(rel, needle):
    hits = [l for l in (ROOT / rel).read_text(encoding="utf-8").split("\n") if needle in l]
    assert hits, (rel, needle)
    return hits


TARGETS = [
    ("src/web/templates/early_access.html", "الحجز المبكر |"),
    ("src/web/templates/early_access.html", "انضم إلى قائمة الوصول المبكر"),
    ("src/web/templates/early_access.html", 'id="eaSubmit"'),
    ("src/services/catalog.py", "أنا موظف خدمة العملاء. أرد على"),
    ("src/services/public_services.py", "تجيب عملاءك"),
    ("src/services/lead_outreach.py", '"ecommerce": "وصف المنتجات'),
]


def test_no_instant_or_24_7_claims():
    for rel, needle in TARGETS:
        for l in _line(rel, needle):
            for b in BANNED:
                assert b not in l, (rel, b)


def test_no_ai_ceo_option():
    assert "AI CEO" not in (ROOT / "src/web/templates/early_access.html").read_text(encoding="utf-8")
