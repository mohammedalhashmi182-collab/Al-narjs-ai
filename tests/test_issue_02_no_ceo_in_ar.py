from pathlib import Path

LANDING = Path(__file__).resolve().parents[1] / "src/web/templates/landing.html"
LINES = LANDING.read_text(encoding="utf-8").split("\n")


def _ar(line):
    return line.split("{% if ar %}", 1)[1].split("{% else %}", 1)[0]


def _find(needle):
    hits = [l for l in LINES if needle in l]
    assert hits, needle
    return hits


def test_arabic_cta_has_no_ceo():
    for l in _find("ناقش هدفك مع"):
        assert "CEO" not in _ar(l)
    for needle in ("يقوده", "يرشّح لك"):
        for l in _find(needle):
            assert "CEO" not in _ar(l)


def test_stage_label_arabic():
    l = _find("تكليف الفريق")[0]
    assert "تشخيص الرئيس التنفيذي" in l and "تشخيص CEO" not in l


def test_avatar_uses_arabic_letter():
    l = _find('class="ceo-avatar"')[0]
    assert "{% if ar %}ر{% else %}CEO{% endif %}" in l


def test_diagnosis_line():
    l = _find("ceo-online")[0]
    assert "An initial diagnosis" in l and "فوري" not in l
