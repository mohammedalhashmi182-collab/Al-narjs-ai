"""Public surfaces use black, white, grey, and #FF5A36.

Green, purple, gold, and beige are rejected by hue, not by a fixed hex list.
Owner-console templates and the dark admin stylesheet are out of scope.
"""
import colorsys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "web"
OWNER_TEMPLATES = {
    "agents.html",
    "base.html",
    "company.html",
    "dashboard.html",
    "executions.html",
    "owner_automation.html",
    "owner_command.html",
    "sales_dashboard.html",
    "sales_demo.html",
    "sales_lead.html",
    "sales_proposal.html",
    "schedules.html",
    "workflows.html",
}
OWNER_CSS = {"narjis-dark-admin.css"}
SUFFIXES = {".css", ".html", ".js", ".svg"}

HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
RGB = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})")
# Known greens the earlier denylist already named. Kept so a near-miss hue still fails.
FORBIDDEN = re.compile(
    r"f4eee2|e9e1d3|bdb4a5|c9a27a|244,\s*238,\s*226|n-green|btn-green"
    r"|#4f7942|#3d5f33|#5ea552|#3f7d3a|#10b981|#34d399|#6ee7b7|#58a052"
    r"|rgba\(\s*16\s*,\s*185\s*,\s*129|rgba\(\s*77\s*,\s*205\s*,\s*94|rgba\(\s*0\s*,\s*212\s*,\s*156"
    r"|rgba\(\s*79\s*,\s*121\s*,\s*66",
    re.I,
)


def _channels(raw: str) -> tuple[int, int, int] | None:
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    try:
        return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return None


def banned_hue(r: int, g: int, b: int) -> str | None:
    """Return a family name when the colour is green, purple, gold, or beige.

    Brand orange (#FF5A36 and its darker text step) stays. Near-white and
    near-grey neutrals stay. Chroma, not HSL saturation, decides beige so a
    one-step warm white such as #F6F5F4 is not treated as ivory.
    """
    chroma = max(r, g, b) - min(r, g, b)
    hue, _light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    hue *= 360
    light = (r + g + b) / (3 * 255)
    if chroma < 18 and not (20 <= hue <= 60 and chroma >= 12 and light >= 0.72):
        return None
    # #FF5A36 is about 11°. Keep the orange action family.
    if 4 <= hue <= 28 and sat >= 0.45 and 0.28 <= light <= 0.72:
        return None
    # Status red and pink sit on the other side of the wheel from orange.
    if (hue <= 8 or hue >= 340) and sat >= 0.2:
        return None
    if 70 <= hue <= 195 and chroma >= 18 and 0.12 <= light <= 0.92:
        return "green"
    if 250 <= hue <= 330 and chroma >= 18 and 0.12 <= light <= 0.92:
        return "purple"
    if 32 <= hue <= 58 and chroma >= 28 and 0.22 <= light <= 0.88:
        return "gold"
    if 20 <= hue <= 60 and chroma >= 12 and light >= 0.72 and sat >= 0.08:
        return "beige"
    return None


def _public_files():
    """Public templates, hand-written public CSS, plus JS and SVG."""
    templates = ROOT / "templates"
    if templates.exists():
        for path in templates.rglob("*.html"):
            if path.name not in OWNER_TEMPLATES:
                yield path
    css = ROOT / "static" / "css"
    if css.exists():
        for path in css.glob("*.css"):
            if path.name in OWNER_CSS or path.name.endswith("-tw.css"):
                continue
            yield path
    for path in ROOT.rglob("*"):
        if path.suffix.lower() in {".js", ".svg"}:
            yield path


def test_public_surfaces_have_no_green_purple_gold_or_beige():
    hits = []
    for path in _public_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(ROOT)
        for number, line in enumerate(text.splitlines(), 1):
            if FORBIDDEN.search(line):
                hits.append(f"{rel}:{number} denylist")
                continue
            colours: list[tuple[int, int, int]] = []
            for match in HEX.finditer(line):
                channels = _channels(match.group(1))
                if channels:
                    colours.append(channels)
            for match in RGB.finditer(line):
                channels = tuple(int(part) for part in match.groups())
                if all(0 <= channel <= 255 for channel in channels):
                    colours.append(channels)  # type: ignore[arg-type]
            for red, green, blue in colours:
                family = banned_hue(red, green, blue)
                if family:
                    hits.append(f"{rel}:{number} {family} rgb({red},{green},{blue})")
                    break
    assert not hits, hits
