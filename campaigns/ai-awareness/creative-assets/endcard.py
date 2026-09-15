# -*- coding: utf-8 -*-
"""Al-Narjis reel end-card (9:16) — single CTA frame for Reels/Stories ads."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arabic_reshaper
from bidi.algorithm import get_display as disp
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
OUT = os.path.join(HERE, "out")
GOLD = (230, 198, 101)
INK = (7, 8, 11)
MUTED = (214, 210, 200)


def shape(t):
    return disp(arabic_reshaper.reshape(t))


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name + ".ttf"), size)


def main():
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    # soft gold glow radial-ish top
    for i in range(60):
        a = int(10 * (1 - i / 60))
        x = W // 2
        y = int(H * 0.32)
        r = int(500 * (i / 60) ** 2)
        d.ellipse((x - r, y - r, x + r, y + r), outline=(GOLD[0], GOLD[1], GOLD[2], a))
    cx = W // 2
    # small brand
    d.text((cx, 150), shape("النرجس للذكاء الاصطناعي"), font=font("Tajawal-Bold", 44), fill=GOLD, anchor="mm")
    d.text((cx, 230), shape("AL-NARJIS AI • RIYADH"), font=font("Tajawal-Regular", 30), fill=MUTED, anchor="mm")
    # big CTA
    d.text((cx, 560), shape("جرّب الآن"), font=font("Tajawal-Black", 130), fill=(255, 255, 244), anchor="mm")
    d.text((cx, 760), shape("فريقك الرقمي يبدأ خلال دقائق"), font=font("Tajawal-Regular", 54), fill=MUTED, anchor="mm")
    # code pill
    code = shape("NARJIS50  •  خصم 50%")
    f = font("Tajawal-Bold", 58)
    bw = f.getbbox(code)[2] + 90
    d.rounded_rectangle((cx - bw / 2, 940, cx + bw / 2, 1060), radius=60, outline=GOLD, width=4)
    d.text((cx, 1000), code, font=f, fill=GOLD, anchor="mm")
    # expiry
    d.text((cx, 1160), shape("ينتهي العرض 14 أكتوبر"), font=font("Tajawal-Regular", 48), fill=MUTED, anchor="mm")
    # bottom logo bar
    d.rectangle((0, H - 300, W, H), fill=(17, 20, 26))
    d.text((cx, H - 240), shape("جرب مجاناً • بدون بطاقة بنكية"), font=font("Tajawal-Bold", 52), fill=(245, 245, 242), anchor="mm")
    d.text((cx, H - 160), shape("karmaai.online"), font=font("Tajawal-Bold", 64), fill=GOLD, anchor="mm")
    os.makedirs(OUT, exist_ok=True)
    img.save(os.path.join(OUT, "endcard_cta_1080x1920.png"), "PNG")
    # also a square version for static-format fallback
    img.save(os.path.join(OUT, "endcard_cta_1080x1080.png"), "PNG")
    print("[ok] endcard_cta_1080x1920.png + endcard_cta_1080x1080.png")


if __name__ == "__main__":
    sys.exit(main())