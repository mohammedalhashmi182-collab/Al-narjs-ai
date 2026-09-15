# -*- coding: utf-8 -*-
"""
Al-Narjis AI — campaign creative builder.
Builds a full library of Arabic (RTL, shaped) ad creatives on brand backgrounds.
Offline rendering: Pillow + arabic_reshaper + python-bidi + Tajawal fonts.
"""
from __future__ import annotations

import io
import os
import sys
import time
import traceback
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
BG_DIR = os.path.join(HERE, "bg")
OUT_DIR = os.path.join(HERE, "out")

W, H = 1080, 1920  # master background size; smaller formats are center-cropped

GOLD = (230, 198, 101)
GOLD_DARK = (168, 130, 55)
GREEN = (14, 92, 63)
INK = (10, 11, 14)
WHITE = (245, 245, 242)
MUTED = (203, 199, 189)

POLL_URL = "https://image.pollinations.ai/prompt/{}?width=1080&height=1920&nologo=true&seed={}"


def load_font(name: str, size: int):
    from PIL import ImageFont
    path = os.path.join(FONTS, name)
    for cand in (path, path + ".ttf"):
        if os.path.exists(cand):
            return ImageFont.truetype(cand, size)
    raise FileNotFoundError(f"missing font {name} in {FONTS}")


def fetch_bg(key: str, prompt: str, seed: int) -> str:
    """Download a 1080x1920 background once (image.pollinations.ai), validate PNG."""
    os.makedirs(BG_DIR, exist_ok=True)
    dest = os.path.join(BG_DIR, key + ".png")
    if os.path.exists(dest) and os.path.getsize(dest) > 10_000:
        return dest
    url = POLL_URL.format(urllib.parse.quote(prompt), seed)
    ok_magic = (b"\x89PNG", b"\xff\xd8\xff")  # PNG or JPEG
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
            if not data.startswith(ok_magic):
                last = f"bad magic {data[:4]}"
                time.sleep(6)
                continue
            from PIL import Image
            Image.open(io.BytesIO(data)).verify()
            with open(dest, "wb") as f:
                f.write(data)
            print(f"  [bg] {key} ok ({len(data)//1024} KB)")
            return dest
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        time.sleep(6)
    raise RuntimeError(f"background {key} failed: {last}")


def cover(bg, target_w, target_h):
    """Center-crop bg image onto canvas of target size (cover fit), no resize distortion."""
    from PIL import Image
    bw, bh = bg.size
    scale = max(target_w / bw, target_h / bh)
    nw, nh = int(round(bw * scale)), int(round(bh * scale))
    bg = bg.resize((nw, nh), Image.LANCZOS)
    x = (nw - target_w) // 2
    y = (nh - target_h) // 2
    return bg.crop((x, y, x + target_w, y + target_h))


def shade(img):
    """Vertical dark gradient overlay for text legibility."""
    from PIL import Image, ImageDraw
    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(h):
        t = y / h
        a = int(120 + 120 * max(0, t - 0.25))
        draw.line([(0, y), (w, y)], fill=(0, 0, 0, min(235, a)))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def shape_ar(text: str) -> str:
    import arabic_reshaper
    from bidi.algorithm import get_display
    return get_display(arabic_reshaper.reshape(text))


def wrap_ar(text: str, font, max_w: int) -> list:
    """Word-wrap Arabic for drawing math; reshape every assembled line."""
    import arabic_reshaper
    from bidi.algorithm import get_display as disp
    words_raw = text.split()
    lines, line = [], []
    for w in words_raw:
        trial = " ".join(line + [w])
        disp_t = disp(arabic_reshaper.reshape(trial))
        width = font.getbbox(disp_t)[2]
        if line and width > max_w:
            lines.append(line)
            line = [w]
        else:
            line.append(w)
    if line:
        lines.append(line)
    return lines


def draw_center(draw, lines, font, y, max_w, fill, leading, cx):
    for ln in lines:
        t = shape_ar(" ".join(ln))
        bbox = draw.fontbbox if hasattr(draw, "fontbbox") else None
        w = font.getbbox(t)[2]
        draw.text((cx - w / 2, y), t, font=font, fill=fill, anchor="la")
        y += leading
    return y


def measure_block(lines, font, leading) -> int:
    if not lines:
        return 0
    return int(leading * len(lines) - (leading - font.size))


def build_variant(bg_path: str, size: tuple, head, sub, cta, badge, seed, name):
    from PIL import Image, ImageDraw

    bg = Image.open(bg_path).convert("RGB")
    canvas = cover(bg, *size)
    canvas = shade(canvas)
    W, H = canvas.size
    draw = ImageDraw.Draw(canvas)

    cx = W // 2
    margin = int(W * 0.10)
    max_tw = W - 2 * margin

    # gold top accent
    draw.rounded_rectangle((cx - 46, int(H * 0.145), cx + 46, int(H * 0.145) + 6), radius=3, fill=GOLD)

    head_size = max(56, int(W * 0.072))
    sub_size = max(30, int(W * 0.042))
    cta_size = max(32, int(W * 0.046))
    badge_size = max(28, int(W * 0.038))

    f_head = load_font("Tajawal-Black", head_size)
    f_sub = load_font("Tajawal-Regular", sub_size)
    f_cta = load_font("Tajawal-Bold", cta_size)
    f_badge = load_font("Tajawal-Bold", badge_size)

    y = int(H * 0.22)
    # headline — two-line emphasis with gold on second line
    head_lines = wrap_ar(head, f_head, max_tw)
    if not head_lines:
        raise ValueError(name + " empty headline")
    paint = True
    for idx, ln in enumerate(head_lines):
        t = shape_ar(" ".join(ln))
        color = GOLD if (paint and idx % 2 == 1) else WHITE
        draw.text((cx, y), t, font=f_head, fill=color, anchor="ma")
        y += int(head_size * 1.28)

    y += int(head_size * 0.55)
    sub_lines = wrap_ar(sub, f_sub, int(max_tw * 0.94))
    y = draw_center(draw, sub_lines, f_sub, y, int(max_tw * 0.94), MUTED, int(sub_size * 1.55), cx)

    # CTA pill
    cta_t = shape_ar(cta)
    cta_w = f_cta.getbbox(cta_t)[2] + 64
    cy = int(H * 0.74)
    draw.rounded_rectangle((cx - cta_w / 2, cy, cx + cta_w / 2, cy + int(H * 0.078)), radius=8, fill=GOLD)
    draw.text((cx, cy + int(H * 0.039)), cta_t, font=f_cta, fill=INK, anchor="mm")

    # badge pill above CTA
    badge_t = shape_ar(badge)
    badge_w = f_badge.getbbox(badge_t)[2] + 44
    by = int(H * 0.665)
    draw.rounded_rectangle((cx - badge_w / 2, by, cx + badge_w / 2, by + int(H * 0.052)), radius=26, outline=GOLD, width=3)
    draw.text((cx, by + int(H * 0.026)), badge_t, font=f_badge, fill=GOLD, anchor="mm")

    # footer
    foot_t = shape_ar("النرجس للذكاء الاصطناعي  •  karmaai.online")
    draw.text((W // 2, H - int(H * 0.05)), foot_t, font=load_font("Tajawal-Regular", max(24, int(W * 0.03))), fill=GOLD, anchor="mm")

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"{name}_{W}x{H}.png")
    canvas.convert("RGB").save(out, "PNG")
    print(f"  [ok] {os.path.basename(out)}")


VARIANTS = [
    # (name, bg_key, size, headline, sub, cta, badge)
    ("meta_cafe", "bg_cafe", (1080, 1350), "التسويق ما عاد ياخد أسبوعك", "وكيل ذكاء اصطناعي يكتب محتوى أسبوعك كامل... وأنت مركز على زبائنك.", "جرّب الآن مجاناً", "NARJIS50 • خصم 50%"),
    ("meta_agents", "bg_agents", (1080, 1350), "فريق ذكي يشتغل 24 ساعة؟", "إيجنتس يكتب المحتوى، يرد على العملاء، ويدير حملاتك — من أي وقت حتى وأنت نايم.", "ابدأ الآن", "خصم 50% بكود NARJIS50"),
    ("meta_city", "bg_city", (1080, 1350), "منافسك في الرياض جرّب... وأنت؟", "أدوات الذكاء الاصطناعي وصلت بالعربي، بدون برمجة. فريقك الرقمي يبدأ خلال دقائق.", "جرّب الآن", "NARJIS50"),
    ("square_hours", "bg_cafe", (1080, 1080), "وفّر أكثر من 10 ساعات أسبوعياً", "بدّل المهام الروتينية بإيجنت ذكي يدير المحتوى والردود بدلاً منك.", "اعرف كيف", "خصم 50% • NARJIS50"),
    ("square_agents", "bg_agents", (1080, 1080), "فريق رقمي كامل... في منصة واحدة", "محتوى، تسويق، متاجر، وخدمة عملاء — بضغطة واحدة وحساب واحد.", "جرّب مجاناً", "بدون بطاقة"),
    ("story_city", "bg_city", (1080, 1920), "أول عميل رقمي؟", "وكيلك الأول جاهز الآن. ابدأ خطوتك الأولى قبل 14 أكتوبر.", "ابدأ الآن", "NARJIS50 • ينتهي 14 أكتوبر"),
    ("story_agents", "bg_agents", (1080, 1920), "من صفر إلى فريق رقمي", "خمس دقائق تفصلك عن وكيلك الأول اللي يشتغل بدلاً منك.", "جرّب الآن", "karmaai.online"),
    ("linkedin_team", "bg_desk", (1200, 1200), "الذكاء الاصطناعي... بالعربي وبساطة", "منصة سعودية تساعد منشأتك تبدأ فريقاً رقمياً واحداً خلال دقائق — لا تحتاج مطوّراً ولا ميزانية ضخمة.", "اكتشف النرجس", "NARJIS50 • خصم 50%"),
    ("x_fomo", "bg_city", (1600, 900), "موجة الذكاء الاصطناعي ما تنتظر أحد", "ابدأ بمشروع صغير اليوم... وكبّره بالقرارات لا بالجهد المضاعف.", "karmaai.online", "خصم 50% حتى 14 أكتوبر"),
    ("wa_offer", "bg_desk", (1080, 1920), "عرض الإطلاق: خصم 50%", "كود NARJIS50 ينتهي 14 أكتوبر. اطلب التفاصيل واحجز لك فريقك الرقمي قبل أي شيء.", "اطلب التفاصيل", "karmaai.online"),
]

BG_PROMPTS = {
    "bg_city": "futuristic Riyadh skyline at night, glowing gold and emerald AI network lines over the city, deep navy luxury cinematic, high-end Saudi tech, no text",
    "bg_cafe": "modern upscale Saudi coffee shop at night, warm golden light, laptop glowing with colorful AI dashboard on the counter, moody dark gold accents, no text",
    "bg_agents": "five glossy glass AI agent orbs floating over a dark luxury desk with holographic dashboard, gold and emerald light, dark premium tech, no text",
    "bg_desk": "dark elegant office desk at night with glowing holographic AI charts and analytics, gold and teal lighting, luxury business technology, no text",
}
BG_SEEDS = {"bg_city": 11, "bg_cafe": 22, "bg_agents": 33, "bg_desk": 44}


def main():
    import urllib.parse
    for key, prompt in BG_PROMPTS.items():
        print(f"[bg] downloading {key} (seed {BG_SEEDS[key]}) ...")
        fetch_bg(key, prompt, BG_SEEDS[key])
    for name, bg_key, size, head, sub, cta, badge in VARIANTS:
        try:
            build_variant(os.path.join(BG_DIR, bg_key + ".png"), size, head, sub, cta, badge, BG_SEEDS[bg_key], name)
        except Exception:
            print(f"  [!!] {name} failed:")
            traceback.print_exc()
    print("Done. Library at", OUT_DIR)


if __name__ == "__main__":
    sys.exit(main())