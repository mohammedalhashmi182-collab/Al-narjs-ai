"""Rasterize the unified Najdi gate mark into the brand files the site serves.

The vector sources under src/web/static are the mark. This script only
exports PNG, WebP, ICO and the social card. It does not invent a second logo.
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"
BRAND = ROOT / "src" / "web" / "brand"
MARK = STATIC / "logo.svg"
INK = (18, 16, 13)
IVORY = (246, 245, 244)
ACCENT = (255, 90, 54)
ARABIC = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"
LATIN = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"


def png(size: int) -> Image.Image:
    raw = cairosvg.svg2png(url=str(MARK), output_width=size, output_height=size)
    return Image.open(io.BytesIO(raw)).convert("RGBA")


def save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)


def wordmark() -> Image.Image:
    image = Image.new("RGBA", (872, 216), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, 871, 215), radius=36, fill=INK + (255,))
    badge = png(168)
    image.paste(badge, (664, 24), badge)
    name = ImageFont.truetype(ARABIC, 78)
    sub = ImageFont.truetype(ARABIC, 36)
    draw.text((640, 78), "النرجس", font=name, fill=IVORY + (255,), anchor="rm", direction="rtl", language="ar")
    draw.text((640, 150), "للذكاء الاصطناعي", font=sub, fill=ACCENT + (255,), anchor="rm", direction="rtl", language="ar")
    return image


def social_card() -> Image.Image:
    image = Image.new("RGB", (1200, 630), INK)
    draw = ImageDraw.Draw(image)
    line = (58, 56, 54)
    draw.rounded_rectangle((48, 40, 1152, 590), radius=28, outline=line, width=2)
    # A stepped Najdi parapet, drawn as a hairline, not a second symbol.
    step = [(72, 520), (72, 430), (150, 430), (150, 340), (228, 340)]
    draw.line(step, fill=line, width=2)
    draw.line([(1128, 110), (1050, 110), (1050, 200), (972, 200), (972, 290)], fill=line, width=2)
    badge = png(196).convert("RGBA")
    image.paste(badge, ((1200 - 196) // 2, 92), badge)
    draw.rectangle((540, 318, 660, 324), fill=ACCENT)
    title = ImageFont.truetype(ARABIC, 64)
    latin = ImageFont.truetype(LATIN, 36)
    draw.text((600, 400), "النرجس للذكاء الاصطناعي", font=title, fill=IVORY, anchor="mm", direction="rtl", language="ar")
    draw.text((600, 478), "NARJIS", font=latin, fill=ACCENT, anchor="mm")
    return image


def write_b64(name: str, data: bytes) -> None:
    (BRAND / f"{name}.b64").write_text(base64.b64encode(data).decode("ascii"), encoding="ascii")


def main() -> None:
    sizes = {
        STATIC / "logo.png": 512,
        STATIC / "favicon.png": 48,
        STATIC / "brand" / "alnarjis-emblem.png": 256,
        STATIC / "brand" / "alnarjis-favicon-32.png": 32,
        STATIC / "brand" / "alnarjis-favicon-48.png": 48,
        STATIC / "brand" / "alnarjis-apple-touch.png": 180,
    }
    encoded: dict[str, bytes] = {}
    for path, size in sizes.items():
        image = png(size)
        save_png(image, path)
        if path.name == "logo.png":
            encoded["logo.png"] = path.read_bytes()
            encoded["icon-512.png"] = encoded["logo.png"]
        elif path.name == "favicon.png":
            encoded["favicon.png"] = path.read_bytes()
        elif path.name == "alnarjis-apple-touch.png":
            encoded["apple-touch-icon.png"] = path.read_bytes()
    icon_192 = png(192)
    buf = io.BytesIO()
    icon_192.save(buf, format="PNG", optimize=True)
    encoded["icon-192.png"] = buf.getvalue()

    emblem = Image.open(STATIC / "brand" / "alnarjis-emblem.png")
    emblem.save(STATIC / "brand" / "alnarjis-emblem.webp", format="WEBP", quality=90, method=6)
    lockup = wordmark()
    save_png(lockup, STATIC / "brand" / "alnarjis-logo.png")
    lockup.save(STATIC / "brand" / "alnarjis-logo.webp", format="WEBP", quality=90, method=6)

    ico = io.BytesIO()
    png(64).save(ico, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    encoded["favicon.ico"] = ico.getvalue()

    card = io.BytesIO()
    social_card().save(card, format="JPEG", quality=86, optimize=True)
    encoded["og-image.jpg"] = card.getvalue()

    for name, data in encoded.items():
        write_b64(name, data)
        print(f"{name} {len(data)}")


if __name__ == "__main__":
    main()
