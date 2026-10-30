from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_addon_notes_not_reveal_hidden():
    t = (ROOT / "src/web/templates/partials/_pricing_section.html").read_text(encoding="utf-8")
    assert "addon-note rv" not in t


def test_compare_mobile_rule():
    css = (ROOT / "src/web/static/css/narjis-najdi.css").read_text(encoding="utf-8")
    assert "@media (max-width:600px){.nj .compare{min-width:0;font-size:13px}.nj .compare th,.nj .compare td{padding:8px}}" in css
