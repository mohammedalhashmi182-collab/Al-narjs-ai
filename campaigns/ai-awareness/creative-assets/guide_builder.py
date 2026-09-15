# -*- coding: utf-8 -*-
"""
Al-Narjis lead magnet — "خطة 30 يوماً" (30-Day AI Quick-Start).
Renders 12 branded 1080x1350 pages (RTL, shaped Arabic) and outputs:
  * guide PDF (multi-page, Pillow → PDF, no extra deps)
  * carousel PNG set (ready for Meta/LinkedIn carousel ads)
"""
import os
import sys

import arabic_reshaper
from bidi.algorithm import get_display as disp
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
OUT = os.path.join(HERE, "guide")
GOLD = (230, 198, 101)
INK = (10, 11, 14)
PAPER = (250, 248, 242)
GREEN = (14, 92, 63)
MUTED = (150, 144, 130)

W, H = 1080, 1350
MARGIN = 96


def shape(t):
    return disp(arabic_reshaper.reshape(t))


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name + ".ttf"), size)


def wrap(text, f, max_w):
    words = text.split()
    lines, cur = [], []
    for w in words:
        trial = " ".join(cur + [w])
        if cur and f.getbbox(shape(trial))[2] > max_w:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    return lines


def new_canvas(color=PAPER):
    img = Image.new("RGB", (W, H), color)
    d = ImageDraw.Draw(img)
    # right accent rail
    d.rectangle((0, 0, 22, H), fill=GOLD)
    d.rectangle((22, 0, 40, H), fill=GREEN)
    return img, d


def footer(d, page, total, accent=GREEN):
    d.text((MARGIN, H - 72), shape("النرجس للذكاء الاصطناعي  •  karmaai.online"), font=font("Tajawal-Bold", 30), fill=accent, anchor="ld")
    d.text((W - MARGIN, H - 72), shape(f"{page:02d} / {total}"), font=font("Tajawal-Regular", 30), fill=MUTED, anchor="rd")


def kicker(d, text):
    d.text((MARGIN, 70), shape(text), font=font("Tajawal-Bold", 40), fill=GREEN, anchor="ld")
    d.line((MARGIN, 120, MARGIN + 210, 120), fill=GOLD, width=6)


def title(d, text, size=74):
    f = font("Tajawal-Black", size)
    d.text((MARGIN, 170), shape(text), font=f, fill=INK, anchor="la")


def bullets(d, items, start_y=380, gap=118, size=44):
    f = font("Tajawal-Regular", size)
    y = start_y
    for it in items:
        for ln in wrap(it, f, W - 2 * MARGIN - 70):
            d.ellipse((MARGIN + 8, y + 22, MARGIN + 8 + 16, y + 22 + 16), fill=GOLD)
            d.text((MARGIN + 60, y), shape(ln), font=f, fill=(40, 36, 30), anchor="la")
            y += int(size * 1.55)
    return y


def cta_page(d, page, total):
    img, draw = new_canvas(INK)
    d = draw
    kicker2 = shape("ابدأ الآن")
    f = font("Tajawal-Black", 96)
    d.text((W // 2, 300), shape("جاهز تبدأ خطوتك الأولى؟"), font=f, fill=(255, 255, 244), anchor="mm")
    d.text((W // 2, 500), shape("ادخل من الآن — دقيقة واحدة وتكون بفريقك الرقمي."), font=font("Tajawal-Regular", 48), fill=(214, 210, 200), anchor="mm")
    code = shape("NARJIS50  •  خصم 50%")
    f2 = font("Tajawal-Bold", 60)
    bw = f2.getbbox(code)[2] + 90
    d.rounded_rectangle((W // 2 - bw / 2, 720, W // 2 + bw / 2, 850), radius=62, outline=GOLD, width=4)
    d.text((W // 2, 785), code, font=f2, fill=GOLD, anchor="mm")
    d.text((W // 2, 950), shape("karmaai.online"), font=font("Tajawal-Bold", 72), fill=GOLD, anchor="mm")
    d.text((W // 2, 1080), shape("ما تحتاجه قوة ذكية... والدفعة التالية قرارك أنت."), font=font("Tajawal-Regular", 40), fill=(214, 210, 200), anchor="mm")
    footer(d, page, total, accent=GOLD)
    return img


PAGES = [
    # cover
    {
        "cover": True,
        "kicker": "دليل مجاني — برعاية النرجس للذكاء الاصطناعي",
        "title": "خطة 30 يوماً",
        "sub": "لأصحاب المشاريع الصغيرة: كيف تحوّل أعمالك بالذكاء الاصطناعي — خطوة بخطوة وبالعربي.",
        "cta": "خالية من التعقيد • تطبق من اليوم الأول",
    },
    {
        "kicker": "لماذا الآن",
        "title": "الذكاء الاصطناعي ما عاد ترفاً",
        "bullets": [
            "المنافسين الأصغر صاروا ينجزون أعمال 3 موظفين بأدوات متاحة من الجوال.",
            "المحتوى المتكرر، الردود الليلية، واقتراحات المتجر — كلها صارت آليّة.",
            "كل تأخير = مكسب يذهب لمنافسك. التغيير يبدأ بقرار صغير اليوم.",
        ],
    },
    {
        "kicker": "فريقك الرقمي",
        "title": "أربعة إيجنتس = فريق كامل",
        "bullets": [
            "إيجنت سوشيال: يخطط وينشر محتواك على المواعيد.",
            "إيجنت متاجر: يرفع المنتجات ويحدّث الأسعار والكوبونات.",
            "إيجنت تسويق: يدير الحملات الإعلانية والخصومات.",
            "إيجنت محتوى: يصنع نصوصاً وردوداً بعلامتك التجارية.",
        ],
    },
    {
        "kicker": "قبل البدء",
        "title": "ماذا تحتاج فعلاً؟",
        "bullets": [
            "حساب واحد على النرجس + منصاتك الحالية (يمكن استعمال واحدة فقط).",
            "خطة الأسبوع: ضع هدفاً واحداً واضحاً (محتوى، ردود، أو مبيعات).",
            "لا تحتاج برمجة ولا شراء أدوات إضافية في البداية.",
            "مجموع الوقت المطلوب يومياً: أقل من 20 دقيقة.",
        ],
    },
    {
        "kicker": "الأسبوع الأول",
        "title": "1) فريقك يستفيق",
        "bullets": [
            "اليوم 1–2: أنشئ حسابك وفعّل إيجنت المحتوى.",
            "اليوم 3: اربط منصتك وأعطِ الإيجنت نغمة علامتك التجارية.",
            "اليوم 4–5: راجع 3 منشورات مجدولة — صحّح وأعجب بما ينتجه.",
            "اليوم 6–7: انشر أول أسبوع آلي، ولاحظ كم ثلاثين دقيقة توفرت.",
        ],
    },
    {
        "kicker": "الأسبوع الثاني",
        "title": "2) ردود وخدمة عملاء",
        "bullets": [
            "فعّل الرد الآلي على الرسائل الشائعة (سعر، المواعيد، التوصيل).",
            "أضف إجاباتك الخاصة ليقلدها الإيجنت بنفس أسلوبك.",
            "خفّف ضغط الموظفين: لا شيء يترك عميلاً ينتظر.",
            "حدد ساعات العمل الآلي ليتناسب مع عطلتك أو دوامك.",
        ],
    },
    {
        "kicker": "الأسبوع الثالث",
        "title": "3) متجر وأسعار ذكية",
        "bullets": [
            "ارفع منتجاتك عبر إيجنت المتاجر دفعة واحدة.",
            "فعّل تحديث الأسعار اليومي حسب سياسة التخفيضات لديك.",
            "طبّق كوبون الشكر التلقائي بعد كل شراء.",
            "راقب أبرز المنتجات وضاعف ترتيبها في خلاصتك.",
        ],
    },
    {
        "kicker": "الأسبوع الرابع",
        "title": "4) القياس والتحسين",
        "bullets": [
            "راجع لوحة النتائج: منشورات، ردود، زيارات، مبيعات.",
            "احتفظ بما عمل وعدّل ما لم يعمل — قرارات بيانات لا تخمين.",
            "ارفع سقف المهام إلى الإيجنتات تدريجياً.",
            "احجز أسبوعاً خامساً: أضف إيجنت تسويق الحملات.",
        ],
    },
    {
        "kicker": "قواعد النجاح",
        "title": "5 عادات لمنشأة تتفوق",
        "bullets": [
            "الاستمرارية: 5 أيام خفيفة أفضل من يوم حماسي واحد.",
            "القياس أسبوعياً بنفس المقياس (لا تغيّره كل مرة).",
            "استعمل ميزة الردود لغرس صوتك، ثم حرر الوقت للجودة.",
            "كل 500 ريال تدخرها من الجهد التشغيلي = نمو + 500 ريال تسويق.",
            "صحّح الأخطاء بسرعة، ولا تنتظر الكمال — أطلق اليوم، حسن غداً.",
        ],
    },
    {
        "kicker": "خريطة 30 يوم",
        "title": "الجدول السريع",
        "bullets": [
            "أسبوع 1: محتوى آلي + أول 3 منشورات.",
            "أسبوع 2: ردود آلية + نغمة صوت موحدة.",
            "أسبوع 3: متجر وآسعار وكوبونات تلقائية.",
            "أسبوع 4: تحسين بالبيانات + إيجنت تسويق.",
            "النتيجة: فريق رقمي يعمل بينما تنتقل شركتك نحو الهدف التالي.",
        ],
    },
    {
        "kicker": "أين كل هذا؟",
        "title": "منصة واحدة تكفي",
        "bullets": [
            "كل الإيجنتات تدار من لوحة واحدة بالعربي.",
            "جدولة تلقائية بأوقات الرياض، وعمل يتوقف إذا طلبت.",
            "سياساتك تحكم: لا رد خارج نطاقك، ولا نشر بدون موافقة.",
            "قابل للتوسع: من مشروع صغير إلى فريق متكامل بنفس الحساب.",
        ],
    },
]

TOTAL = len(PAGES) + 1  # + back cover CTA


def build():
    os.makedirs(OUT, exist_ok=True)
    imgs = []
    for i, p in enumerate(PAGES, start=1):
        if p.get("cover"):
            img, d = new_canvas(INK)
            d.text((W // 2, 240), shape("النرجس للذكاء الاصطناعي"), font=font("Tajawal-Bold", 58), fill=GOLD, anchor="mm")
            d.text((W // 2, 330), shape("AL-NARJIS AI • RIYADH"), font=font("Tajawal-Regular", 34), fill=(214, 210, 200), anchor="mm")
            d.rectangle((MARGIN, 560, W - MARGIN, 568), fill=GOLD)
            d.text((W // 2, 720), shape(p["title"]), font=font("Tajawal-Black", 150), fill=(255, 255, 244), anchor="mm")
            subf = font("Tajawal-Regular", 48)
            for ln in wrap(p["sub"], subf, W - 2 * MARGIN - 60):
                d.text((W // 2, 1020), shape(ln), font=subf, fill=(214, 210, 200), anchor="mm")
                pass
            d.text((W // 2, 1180), shape(p["cta"]), font=font("Tajawal-Bold", 44), fill=GOLD, anchor="mm")
            footer(d, 1, TOTAL, accent=GOLD)
        else:
            img, d = new_canvas(PAPER)
            kicker(d, p["kicker"])
            for ln in wrap(p["title"], font("Tajawal-Black", 74), W - 2 * MARGIN):
                pass
            f = font("Tajawal-Black", 74) if len(p["title"]) <= 28 else font("Tajawal-Black", 60)
            d.text((MARGIN, 190), shape(p["title"]), font=f, fill=INK, anchor="la")
            bullets(d, p.get("bullets", []), start_y=420, size=44)
            footer(d, i, TOTAL)
        out = os.path.join(OUT, f"page_{i:02d}.png")
        img.save(out, "PNG")
        imgs.append(img.convert("RGB"))
        print("[ok]", os.path.basename(out))

    # back cover = CTA
    back = cta_page(d, TOTAL, TOTAL)
    back_path = os.path.join(OUT, f"page_{TOTAL:02d}.png")
    back.save(back_path, "PNG")
    imgs.append(back.convert("RGB"))
    print("[ok]", os.path.basename(back_path))

    pdf = os.path.join(OUT, "narjis-30day-ai-guide.pdf")
    imgs[0].save(pdf, "PDF", save_all=True, append_images=imgs[1:], resolution=150)
    print("[ok]", pdf, os.path.getsize(pdf) // 1024, "KB")
    print(f"Slides: {TOTAL} pages → carousel ads / PDF lead magnet")


if __name__ == "__main__":
    sys.exit(build())