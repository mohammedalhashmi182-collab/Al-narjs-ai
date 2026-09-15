#!/usr/bin/env python3
"""
توليد باقة أسبوع من حملة التوعية عبر نفس إيجنتس المنصة (agents/base/*.yaml).

الاستخدام:
    python campaigns/ai-awareness/generate_week.py [week_number] [model]

مثال:
    python campaigns/ai-awareness/generate_week.py 1
"""

import json
import re
import sys
import time
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[2]
CAMP = ROOT / "campaigns" / "ai-awareness"
CONFIG = json.loads((CAMP / "config.json").read_text(encoding="utf-8"))

DEFAULT_MODEL = "gemini-3.6-flash"


def env_key(key: str) -> str:
    try:
        text = (ROOT / ".env").read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    m = re.search(rf"^{re.escape(key)}=(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


GEMINI_KEY = env_key("GEMINI_API_KEY")
MOONSHOT_KEY = env_key("MOONSHOT_API_KEY")
MOONSHOT_BASE = env_key("MOONSHOT_BASE_URL") or "https://api.moonshot.ai/v1"
MOONSHOT_MODEL = env_key("MOONSHOT_DEFAULT_MODEL") or "kimi-k2.7-code"


def load_agent(slug: str) -> dict:
    path = ROOT / "agents" / "base" / f"{slug}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


AGENTS = {slug: load_agent(slug) for slug in ("content_writer", "social_media", "marketing_agent", "localization")}


def context_block() -> str:
    b = CONFIG["brand"]
    r = CONFIG["region"]
    a = CONFIG["audience"]
    lines = [
        "معلومات الحملة (ثابتة لكل توليد):",
        f"- المسبق: من {b['founder']} — مؤسس {b['platform_name']} ({b['platform_url']}).",
        f"- النطاق الجغرافي: {r['scope']}، وفّقها مع {r['country_focus']}، واستخدم أمثلة من {r['city_focus']}.",
        f"- أمثلة محلية مقترحة: {'، '.join(r['examples_to_use'])}.",
        f"- الجمهور الأساسي: {a['primary']}.",
        f"- نبرة: {CONFIG['tone']}.",
        f"- ركائز: {'؛ '.join(CONFIG['pillars'])}.",
        f"- CTA: {CONFIG['cta']['primary']}.",
        f"- الهاشتاجات: {' '.join(CONFIG['hashtags'])}.",
        "",
        "قواعد حاسمة:",
        "- اكتب بالعربية السليمة الفصحى السهلة، بلا مصطلحات معقدة.",
        "- لا تقدم وعوداً بنسب مضمونة أو أرقام خيالية.",
        "- لا أنكر أن الأدوات أجنبية، لكن قدّم قيمة محلية.",
        "- استشهد بالهيئات فقط بشكل عام (مثل هيئة البيانات والذكاء الاصطناعي SDAIA) دون ادعاء نسب إليها.",
        "- ختام كل قطعة: توقيع 'محمد الهاشمي' وذكر karmaai.online بشكل طبيعي.",
    ]
    return "\n".join(lines)


def agent_system(slug: str, extra: str = "") -> str:
    agent = AGENTS[slug]
    prompt = agent["prompts"].get("default", "")
    return f"{agent['name']}\n\n{prompt}\n\n{extra}"


PROVIDER = "gemini"  # toggled via CLI arg "moonshot"


def ask(system: str, user: str, temperature: float = 0.7, max_tokens: int = 1800, model: str = DEFAULT_MODEL) -> str:
    if PROVIDER == "moonshot":
        return ask_moonshot(system, user, temperature, max_tokens, model)
    return ask_gemini(system, user, temperature, max_tokens, model)


def ask_moonshot(system: str, user: str, temperature: float, max_tokens: int, model: str) -> str:
    if not MOONSHOT_KEY:
        raise RuntimeError("MOONSHOT_API_KEY غير موجود في .env")
    user = user + "\n\nبشكل قاطع: أرسل النص النهائي كاملاً فقط — بدون مقدمة، بدون ملاحظات، بدون خطط، بدون عناوين شرح."
    waits = 0
    with httpx.Client(timeout=240) as client:
        for attempt in range(6):
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            try:
                resp = client.post(
                    f"{MOONSHOT_BASE.rstrip('/')}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {MOONSHOT_KEY}"},
                )
            except httpx.TransportError as exc:
                print(f"  ... خطأ شبكة ({exc.__class__.__name__}) → ننتظر 20 ثانية ثم نعيد")
                time.sleep(20)
                continue
            data = resp.json()
            if resp.status_code == 429:
                if waits > 8:
                    raise RuntimeError("حصة Moonshot مستنزفة — جرب لاحقاً")
                waits += 1
                print("  ... 429 → ننتظر 45 ثانية ثم نعيد")
                time.sleep(45)
                continue
            if resp.status_code != 200 or not data.get("choices"):
                raise RuntimeError(f"Moonshot {resp.status_code}: {json.dumps(data, ensure_ascii=False)[:400]}")
            text = (data["choices"][0].get("message", {}).get("content", "") or "").strip()
            finish = data["choices"][0].get("finish_reason", "")
            if finish == "length" and attempt < 5:
                max_tokens = int(max_tokens * 1.8)
                print("  ... الناتج قُصّ → نعيد بميزانية رموز أكبر")
                continue
            return text
    raise RuntimeError("لم نتمكن من إكمال التوليد بعد عدة محاولات (Moonshot)")


def ask_gemini(system: str, user: str, temperature: float, max_tokens: int, model: str) -> str:
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY غير موجود في .env")
    user = user + "\n\nبشكل قاطع: أرسل النص النهائي كاملاً فقط — بدون مقدمة، بدون ملاحظات، بدون خطط، بدون عناوين شرح."
    quota_waits = 0
    max_attempts = 5
    with httpx.Client(timeout=240) as client:
        for attempt in range(max_attempts):
            payload = {
                "contents": [{"role": "user", "parts": [{"text": f"{system}\n\n{user}"}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
            }
            try:
                resp = client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}",
                    json=payload,
                )
            except httpx.TransportError as exc:
                print(f"  ... خطأ شبكة ({exc.__class__.__name__}) → ننتظر 20 ثانية ثم نعيد")
                time.sleep(20)
                continue
            data = resp.json()
            if resp.status_code == 429:
                if quota_waits > 8:
                    raise RuntimeError("قيمة الحصة المجانية مستنزفة — جرب مرة أخرى لاحقاً أو استخدم مفتاحاً مدفوعاً")
                quota_waits += 1
                wait = 60
                print(f"  ... 429 (حد الطلبات المجانية) → ننتظر {wait} ثانية ثم نعيد")
                time.sleep(wait)
                continue
            if resp.status_code != 200 or not data.get("candidates"):
                raise RuntimeError(f"Gemini {resp.status_code}: {json.dumps(data, ensure_ascii=False)[:400]}")
            cand = data["candidates"][0]
            finish = cand.get("finishReason", "")
            parts = [p.get("text", "") for p in cand.get("content", {}).get("parts", []) if p.get("text")]
            text = "\n".join(parts).strip()
            if finish == "MAX_TOKENS" and attempt < max_attempts - 1:
                max_tokens = int(max_tokens * 1.8)
                print("  ... الناتج قُصّ → نعيد بميزانية رموز أكبر")
                continue
            return text
    raise RuntimeError("لم نتمكن من إكمال التوليد بعد عدة محاولات")


def generate_linkedin(theme, goal, model):
    system = agent_system("content_writer",
                          "أنت في مهمة توعوية وليست بيعية مبكرة: قدّم قيمة كاملة أولاً، والـCTA الناعم في النهاية فقط.")
    user = f"""اكتب منشور LinkedIn طويل (300-450 كلمة) بالعربية حول هذا الموضوع الأسبوعي:
- الموضوع: {theme}
- الهدف: {goal}
- الشكل: عنوان جاذب، فقرة افتتاح بالخاطف، 3 نقاط عملية مع مثال رياضي، نهاية بملخص ونعومة CTA (karmaai.online).
{context_block()}
اكتب المنشور الآن كاملاً دون مقدمات."""
    return ask(system, user, temperature=0.8, max_tokens=2400, model=model)


def generate_twitter(theme, model):
    system = agent_system("social_media", "أنت كاتب تغريدات عربية قصيرة مؤثرة.")
    user = f"""اكتب 5 تغريدات لـX/تويتر حول: {theme}
لكل تغريدة: نص واحد (ما بين 90 و180 حرفاً) + هاشتاج واحد ذي صلة، ثم سطر جديد.
عادة ابدأ البعض بسؤال، والبعض بجملة استفزازية لطيفة، وجميعها بهاشتاجات الخليج/السعودية/الرياض.
{context_block()}"""
    return ask(system, user, temperature=0.85, max_tokens=2200, model=model)


def generate_newsletter(theme, goal, model):
    system = agent_system("localization",
                          "أنت كاتب نشرة بريدية لطيفة شخصية بأسلوب المحمد الهاشمي، تُقرأ بالعربية بسلاسة تماماً.")
    user = f"""اكتب نشرة بريدية أسبوعية قصيرة (250-350 كلمة) حول: {theme}
باجتماع: موضوع مباشر، قصّه قصيرة من الرياض، قسم 'جرّب اليوم بخطوة واحدة'، ثم توقيع المؤسس.
{context_block()}"""
    return ask(system, user, temperature=0.75, max_tokens=2000, model=model)


def generate_video_script(theme, model):
    system = agent_system("marketing_agent", "أنت كاتب سكربتات فيديو قصيرة (ريلز) بافتتاحية قوية.")
    user = f"""اكتب سكربت فيديو قصير (45-60 ثانية) حول: {theme}
بالتصميم:
- HOOK (أول 3 ثواني: جملة توقف السكرول)
- 3 نقاط سريعة بأمثلة رياضية
- CTA شفهي + نصي (karmaai.online)
- أسطر الشاشة/Subtitles المقترحة والعربية
{context_block()}"""
    return ask(system, user, temperature=0.8, max_tokens=2400, model=model)


def generate_carousel(theme, model):
    system = agent_system("content_writer", "أنت مصمم محتوى كاروزيل تعليمي.")
    user = f"""صمم كاروزيل تعليمي من 5 شرائح حول: {theme}
لكل شريحة: العنوان (اقل من 10 كلمات) + نص الشريحة (اقل من 25 كلمة) + متطلب بصري (صورة/أيقونة).
{context_block()}"""
    return ask(system, user, temperature=0.75, max_tokens=2400, model=model)


def main():
    week_arg = sys.argv[1] if len(sys.argv) > 1 else "1"
    model = DEFAULT_MODEL
    only = []
    for arg in sys.argv[2:]:
        if arg == "moonshot":
            global PROVIDER
            PROVIDER = "moonshot"
            continue
        if arg.count(":") == 1 and not arg.startswith("gemini") and arg.split(":")[0].isalpha():
            continue
        if arg in ("gemini-3.6-flash",):
            model = arg
        else:
            only.append(arg)
    try:
        week_num = int(re.search(r"\d+", week_arg).group())
    except Exception:
        week_num = 1
    try:
        meta = next(w for w in CONFIG["weeks"] if w["week"] == week_num)
    except StopIteration:
        print(f"الأسبوع {week_num} غير موجود في config.json")
        sys.exit(1)

    out = CAMP / "packs" / f"week-{week_num:02d}"
    out.mkdir(parents=True, exist_ok=True)

    theme, goal = meta["theme"], meta["goal"]
    tasks = {
        "linkedin_post.md": (generate_linkedin, (theme, goal, model)),
        "twitter_posts.md": (generate_twitter, (theme, model)),
        "email_newsletter.md": (generate_newsletter, (theme, goal, model)),
        "video_script_60s.md": (generate_video_script, (theme, model)),
        "carousel_outline.md": (generate_carousel, (theme, model)),
    }

    print(f"توليد باقة الأسبوع {week_num}: {theme}")
    for name, (fn, args) in tasks.items():
        if only and name not in only:
            continue
        print(f"  ... {name}")
        text = fn(*args)
        (out / name).write_text(text, encoding="utf-8")

    manifest = {"week": week_num, "theme": theme, "goal": goal,
                "model": model, "region": CONFIG["region"],
                "brand": CONFIG["brand"], "hashtags": CONFIG["hashtags"],
                "files": list(tasks)}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nتم بنجاح → {out}")


if __name__ == "__main__":
    main()