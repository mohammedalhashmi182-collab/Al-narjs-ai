"""Build the Narjis wordmark as outlined paths and the raster brand files.

The Arabic is نoto Kufi Black (OFL), shaped with HarfBuzz so «النرجس» keeps
its real joins: isolated alif, initial lam, medial nun, final reh, initial
jeem, final seen. The nun dot is a diamond filled from --nj-accent to --nj-accent-2 in
narjis-palette.css. The square icon is that diamond alone, because the
word does not read at 32px.
"""
from __future__ import annotations

import base64
import io
import re
from pathlib import Path

import cairosvg
import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"
BRAND = ROOT / "src" / "web" / "brand"
VAR_FONT = Path("/tmp/fonts/NotoKufiArabic-var.ttf")
KUFI = Path("/tmp/fonts/NotoKufi-Black.ttf")
LATIN_FONT = Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf")

CHAMFER = 96
PALETTE = ROOT / "src" / "web" / "static" / "css" / "narjis-palette.css"


def _token(name: str) -> str:
    text = PALETTE.read_text(encoding="utf-8")
    match = re.search(rf"{re.escape(name)}:\s*(#[0-9A-Fa-f]{{6}})", text)
    if not match:
        raise SystemExit(f"missing {name} in {PALETTE}")
    return match.group(1)


def _colors() -> tuple[str, str, str, str]:
    return (
        _token("--nj-text"),
        _token("--nj-text-on-light"),
        _token("--nj-accent"),
        _token("--nj-accent-2"),
    )


def _kufi() -> None:
    if not VAR_FONT.exists():
        raise SystemExit("missing variable Noto Kufi font at /tmp/fonts/NotoKufiArabic-var.ttf")
    instantiateVariableFont(TTFont(VAR_FONT), {"wght": 900}, inplace=False).save(KUFI)


def _shape(font_path: Path, text: str, script: str, direction: str, language: str):
    blob = hb.Blob.from_file_path(str(font_path))
    face = hb.Face(blob)
    font = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.direction = direction
    buf.script = script
    buf.language = language
    hb.shape(font, buf)
    tt = TTFont(font_path)
    return tt, buf


def _chamfer_alif(commands: str) -> str:
    """The isolated alif is a rectangle. Cut every corner at 45 degrees."""
    c = CHAMFER
    return (
        f"M100 {760 - c}L{100 + c} 760L{289 - c} 760L289 {760 - c}"
        f"L289 {c}L{289 - c} 0L{100 + c} 0L100 {c}Z"
    )


def _chamfer_lam(commands: str) -> str:
    """Cut the square top of the lam ascender. The join at the baseline stays."""
    c = CHAMFER
    return commands.replace(
        "H115V760H304V0",
        f"H115V{760 - c}L{115 + c} 760H{304 - c}L304 {760 - c}V0",
    )


def arabic_groups(ink: str) -> tuple[str, str, tuple[float, float, float, float]]:
    tt, buf = _shape(KUFI, "النرجس", "Arab", "rtl", "ar")
    gs = tt.getGlyphSet()
    order = tt.getGlyphOrder()
    parts: list[str] = []
    diamond = None
    minx = miny = 10**9
    maxx = maxy = -10**9
    x = y = 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        name = order[info.codepoint]
        gx = x + pos.x_offset
        gy = y + pos.y_offset
        bounds = BoundsPen(gs)
        gs[name].draw(bounds)
        if name == "dotabovear" and bounds.bounds:
            box = bounds.bounds
            diamond = (
                gx + (box[0] + box[2]) / 2,
                gy + (box[1] + box[3]) / 2,
                max(box[2] - box[0], box[3] - box[1]),
            )
        else:
            pen = SVGPathPen(gs)
            gs[name].draw(pen)
            commands = pen.getCommands()
            if name == "uni0627":
                commands = _chamfer_alif(commands)
            elif name == "uni0644.init":
                commands = _chamfer_lam(commands)
            if commands:
                parts.append(
                    f'<g transform="translate({gx:.2f} {gy:.2f})"><path d="{commands}"/></g>'
                )
            if bounds.bounds:
                box = bounds.bounds
                minx = min(minx, gx + box[0])
                maxx = max(maxx, gx + box[2])
                miny = min(miny, gy + box[1])
                maxy = max(maxy, gy + box[3])
        x += pos.x_advance
        y += pos.y_advance
    if diamond is None:
        raise SystemExit("the nun dot glyph was not found")
    cx, cy, size = diamond
    reach = size * 0.62
    # Keep the jewel inside the view, above the nun.
    minx = min(minx, cx - reach)
    maxx = max(maxx, cx + reach)
    miny = min(miny, cy - reach)
    maxy = max(maxy, cy + reach)
    body = f'<g fill="{ink}">{"".join(parts)}</g>'
    # Font y grows up. The diamond is drawn in that same space, then flipped.
    gem = (
        f'<path fill="url(#narjis-noon)" d="M{cx:.2f} {cy + reach:.2f} '
        f'L{cx + reach:.2f} {cy:.2f} L{cx:.2f} {cy - reach:.2f} L{cx - reach:.2f} {cy:.2f} Z"/>'
    )
    return body, gem, (minx, miny, maxx, maxy)


def latin_group(ink: str, target_width: float) -> tuple[str, float, float, float]:
    """Outlined Latin. Returns the group, scale, font-space top, and font-space bottom."""
    tt, buf = _shape(LATIN_FONT, "AL-NARJIS AI", "Latn", "ltr", "en")
    gs = tt.getGlyphSet()
    order = tt.getGlyphOrder()
    tracking = 140
    parts: list[str] = []
    x = 0.0
    miny = 10**9
    maxy = -10**9
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        name = order[info.codepoint]
        pen = SVGPathPen(gs)
        gs[name].draw(pen)
        commands = pen.getCommands()
        bounds = BoundsPen(gs)
        gs[name].draw(bounds)
        if commands:
            parts.append(f'<g transform="translate({x + pos.x_offset:.2f} 0)"><path d="{commands}"/></g>')
        if bounds.bounds:
            miny = min(miny, bounds.bounds[1])
            maxy = max(maxy, bounds.bounds[3])
        step = pos.x_advance + (tracking if name != "space" else 80)
        x += step
    scale = target_width / x if x else 1
    group = f'<g fill="{ink}" transform="scale({scale:.5f})">{"".join(parts)}</g>'
    return group, scale, maxy, miny


def wordmark_svg(*, ink: str, plate: str | None) -> str:
    body, gem, (minx, miny, maxx, maxy) = arabic_groups(ink)
    width = maxx - minx
    latin, latin_scale, latin_top, latin_bottom = latin_group(ink, width * 0.72)
    pad_x = 80
    pad_top = 70
    gap = 110
    pad_bottom = 48
    arabic_h = maxy - miny
    latin_h = (latin_top - latin_bottom) * latin_scale
    total_w = width + pad_x * 2
    total_h = pad_top + arabic_h + gap + latin_h + pad_bottom
    # Flip the Arabic from font space into the view.
    arabic_tx = pad_x - minx
    arabic_ty = pad_top + maxy
    latin_tx = (total_w - width * 0.72) / 2
    # Baseline sits so the cap top begins after the gap. scale(1,-1) turns font-up into SVG-up.
    latin_ty = pad_top + arabic_h + gap + latin_top * latin_scale
    accent, accent_2 = _colors()[2:]
    plate_rect = f'<rect width="{total_w:.2f}" height="{total_h:.2f}" fill="{plate}"/>' if plate else ""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w:.2f} {total_h:.2f}" role="img" aria-label="النرجس AL-NARJIS AI">
<defs><linearGradient id="narjis-noon" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="{accent}"/><stop offset="1" stop-color="{accent_2}"/></linearGradient></defs>
{plate_rect}<g transform="translate({arabic_tx:.2f} {arabic_ty:.2f}) scale(1 -1)">{body}{gem}</g>
<g transform="translate({latin_tx:.2f} {latin_ty:.2f}) scale(1 -1)">{latin}</g>
</svg>
'''


def diamond_svg(size: int = 100) -> str:
    inset = 28
    mid = size / 2
    _, ink, accent, accent_2 = _colors()
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" role="img" aria-label="النرجس">
<defs><linearGradient id="narjis-noon" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="{accent}"/><stop offset="1" stop-color="{accent_2}"/></linearGradient></defs>
<rect width="{size}" height="{size}" rx="{round(size * 0.22)}" fill="{ink}"/>
<path fill="url(#narjis-noon)" d="M{mid} {inset} L{size - inset} {mid} L{mid} {size - inset} L{inset} {mid} Z"/>
</svg>
'''


def mono_svg() -> str:
    svg = wordmark_svg(ink="#000000", plate=None)
    return svg.replace('fill="url(#narjis-noon)"', 'fill="#000000"')


def _png(svg: str, width: int, height: int | None = None) -> Image.Image:
    raw = cairosvg.svg2png(bytestring=svg.encode(), output_width=width, output_height=height)
    return Image.open(io.BytesIO(raw)).convert("RGBA")


def _b64(name: str, data: bytes) -> None:
    (BRAND / f"{name}.b64").write_text(base64.b64encode(data).decode("ascii"), encoding="ascii")


def main() -> None:
    _kufi()
    text, ink, _accent, _accent_2 = _colors()
    dark = wordmark_svg(ink=text, plate=None)
    light = wordmark_svg(ink=ink, plate=None)
    dark_plate = wordmark_svg(ink=text, plate=ink)
    light_plate = wordmark_svg(ink=ink, plate="#FFFFFF")
    icon = diamond_svg()
    (STATIC / "logo.svg").write_text(dark, encoding="utf-8")
    (STATIC / "logo-dark.svg").write_text(dark, encoding="utf-8")
    (STATIC / "brand-narjis-gate.svg").write_text(dark, encoding="utf-8")
    (STATIC / "favicon.svg").write_text(icon, encoding="utf-8")
    (STATIC / "brand" / "wordmark-dark.svg").write_text(dark_plate, encoding="utf-8")
    (STATIC / "brand" / "wordmark-light.svg").write_text(light_plate, encoding="utf-8")
    (STATIC / "brand" / "vnext" / "logo-ar.svg").write_text(dark_plate, encoding="utf-8")
    (STATIC / "brand" / "vnext" / "logo-en.svg").write_text(dark_plate, encoding="utf-8")
    (STATIC / "brand" / "vnext" / "mark-mono.svg").write_text(mono_svg(), encoding="utf-8")
    (STATIC / "brand" / "vnext" / "app-icon.svg").write_text(icon, encoding="utf-8")
    (STATIC / "brand" / "vnext" / "app-icon-maskable.svg").write_text(
        diamond_svg().replace('rx="22"', 'rx="0"').replace('rx="22.0"', ""),
        encoding="utf-8",
    )
    # The maskable icon must fill the canvas; diamond_svg already does, with a radius.
    # A maskable icon keeps the diamond inside the safe area.
    _, ink, accent, accent_2 = _colors()
    safe = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" role="img" aria-label="النرجس">
<defs><linearGradient id="narjis-noon" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="{accent}"/><stop offset="1" stop-color="{accent_2}"/></linearGradient></defs>
<rect width="100" height="100" fill="{ink}"/>
<g transform="translate(14 14) scale(0.72)"><path fill="url(#narjis-noon)" d="M50 18 L82 50 L50 82 L18 50 Z"/></g>
</svg>
'''
    (STATIC / "brand" / "vnext" / "app-icon-maskable.svg").write_text(safe, encoding="utf-8")

    def save(image: Image.Image, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, format="PNG", optimize=True)

    mark = _png(dark_plate, 872)
    # Normalize the wide lockup to the existing 872x216 slot by fitting.
    plate = tuple(int(_colors()[1][i:i + 2], 16) for i in (1, 3, 5)) + (255,)
    fitted = Image.new("RGBA", (872, 216), plate)
    scale = min(820 / mark.width, 180 / mark.height)
    resized = mark.resize((max(1, int(mark.width * scale)), max(1, int(mark.height * scale))), Image.Resampling.LANCZOS)
    fitted.paste(resized, ((872 - resized.width) // 2, (216 - resized.height) // 2), resized)
    save(fitted, STATIC / "brand" / "alnarjis-logo.png")
    fitted.save(STATIC / "brand" / "alnarjis-logo.webp", format="WEBP", quality=90, method=6)

    emblem = _png(icon, 256)
    save(emblem, STATIC / "brand" / "alnarjis-emblem.png")
    emblem.save(STATIC / "brand" / "alnarjis-emblem.webp", format="WEBP", quality=90, method=6)
    save(_png(icon, 32), STATIC / "brand" / "alnarjis-favicon-32.png")
    save(_png(icon, 48), STATIC / "brand" / "alnarjis-favicon-48.png")
    save(_png(icon, 180), STATIC / "brand" / "alnarjis-apple-touch.png")
    save(_png(icon, 512), STATIC / "logo.png")
    save(_png(icon, 48), STATIC / "favicon.png")

    def png_bytes(image: Image.Image) -> bytes:
        buf = io.BytesIO()
        image.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    _b64("logo.png", (STATIC / "logo.png").read_bytes())
    _b64("icon-512.png", (STATIC / "logo.png").read_bytes())
    _b64("favicon.png", (STATIC / "favicon.png").read_bytes())
    _b64("apple-touch-icon.png", (STATIC / "brand" / "alnarjis-apple-touch.png").read_bytes())
    _b64("icon-192.png", png_bytes(_png(icon, 192)))
    ico = io.BytesIO()
    _png(icon, 64).save(ico, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    _b64("favicon.ico", ico.getvalue())

    card = Image.new("RGB", (1200, 630), tuple(int(_colors()[1][i:i + 2], 16) for i in (1, 3, 5)))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((48, 40, 1152, 590), radius=28, outline=(46, 52, 58), width=2)
    lock = _png(dark, 760)
    card.paste(lock, ((1200 - lock.width) // 2, (630 - lock.height) // 2), lock)
    jpg = io.BytesIO()
    card.save(jpg, format="JPEG", quality=88, optimize=True)
    _b64("og-image.jpg", jpg.getvalue())
    print("wordmark written")


if __name__ == "__main__":
    main()
