"""Social media agent: Arabic ad posts + a weekly posting schedule, saved as drafts.

Deterministic copy built from the live catalog (prices, agent counts), so a post
can never quote a price or a result that is not real. Nothing is published:
rows land in ``automation_social_posts`` with status ``draft`` for the owner.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.automation import SocialPostDraft
from src.services import catalog

RIYADH = ZoneInfo("Asia/Riyadh")
BASE_TAGS = ["#النرجس_للذكاء_الاصطناعي", "#رؤية_2030", "#ريادة_الأعمال", "#السعودية"]

# (weekday 0=Mon, local hour, platform, theme, plan) — Saudi evening peak, Fri lighter.
WEEKLY_SLOTS: tuple[tuple[int, int, str, str, str | None], ...] = (
    (6, 20, "instagram", "problem_solution", "bidaya"),  # Sunday
    (0, 21, "linkedin", "vision2030", None),               # Monday
    (1, 20, "x", "plan_spotlight", "bidaya"),              # Tuesday
    (2, 21, "instagram", "how_it_works", None),            # Wednesday
    (3, 20, "tiktok", "plan_spotlight", "numuw"),          # Thursday
    (4, 16, "x", "addon", None),                           # Friday (after prayers)
    (5, 21, "linkedin", "plan_spotlight", "sharikat"),     # Saturday
)


def _sar(halalas: int) -> str:
    return f"{halalas // 100:,}"


def compose_post(theme: str, plan_key: str | None = None) -> str:
    link = "karmaai.online"
    if theme == "plan_spotlight" and plan_key in catalog.PACKAGES:
        pkg = catalog.PACKAGES[plan_key]
        return (f"باقة «{pkg['name']}» 🌟\n"
                f"{_sar(pkg['amount'])} ريال شهرياً، أو {_sar(catalog.plan_amount(plan_key, 'annual'))} ريال سنوياً "
                f"(ادفع 10 أشهر واحصل على 12).\n"
                f"تشمل {pkg['limits']['conversations']:,} محادثة شهرياً، ورسوم ميتا حتى {pkg['limits']['meta_cap'] // 100} ريال.\n"
                f"اكتب لنا مشكلتك ويرشّح لك الرئيس التنفيذي الباقة المناسبة.\n{link}")
    if theme == "problem_solution":
        pkg = catalog.PACKAGES[plan_key or catalog.PACKAGE_ORDER[0]]
        return ("ردود العملاء متأخرة؟ المحتوى متقطّع؟ الإعلانات ما تجيب نتيجة؟ 🤔\n"
                f"ابدأ بباقة «{pkg['name']}» بـ {_sar(pkg['amount'])} ريال شهرياً.\n"
                f"وصف مشكلتك بكلماتك على {link}")
    if theme == "vision2030":
        prices = "، ".join(
            f"«{catalog.PACKAGES[k]['name']}» {_sar(catalog.PACKAGES[k]['amount'])} ريال"
            for k in catalog.PACKAGE_ORDER
        )
        return ("التحول الرقمي من مستهدفات رؤية 2030 🇸🇦\n"
                "في «النرجس» نوفّر للمنشآت الصغيرة والمتوسطة اشتراكاً بالعربي وفاتورة ضريبية.\n"
                f"الباقات: {prices} شهرياً.\n{link}")
    if theme == "how_it_works":
        return ("كيف نشتغل؟ 3 خطوات:\n1️⃣ تكتب مشكلتك بكلماتك\n2️⃣ الرئيس التنفيذي يشخّصها ويرشّح الباقة\n"
                f"3️⃣ تشترك ونبدأ التجهيز\nجرّبها الحين على {link}")
    if theme == "addon":
        add = _sar(catalog.ADDON_AGENT["amount"])
        return (f"فريقك يحتاج يد زيادة؟ 💪 أضف أي وكيل ذكاء اصطناعي لباقتك بـ {add} ريال شهرياً فقط، بدون تغيير باقتك.\n{link}")
    raise ValueError(f"unknown theme {theme}")


def week_start(today: date | None = None) -> date:
    """The coming Sunday (Saudi week start), or today if it is Sunday."""
    today = today or datetime.now(RIYADH).date()
    return today + timedelta(days=(6 - today.weekday()) % 7)


def weekly_schedule(start: date | None = None) -> list[dict]:
    start = start or week_start()
    out = []
    for weekday, hour, platform, theme, plan in WEEKLY_SLOTS:
        day = start + timedelta(days=(weekday - 6) % 7)
        local = datetime.combine(day, time(hour, 0), tzinfo=RIYADH)
        out.append({
            "platform": platform, "theme": theme, "plan_key": plan,
            "scheduled_for": local.astimezone(UTC), "local_time": local.strftime("%A %Y-%m-%d %H:%M"),
            "text": compose_post(theme, plan), "hashtags": list(BASE_TAGS),
        })
    return sorted(out, key=lambda r: r["scheduled_for"])


async def generate_week(session: AsyncSession, start: date | None = None) -> list[SocialPostDraft]:
    """Save one week of posts as drafts (idempotent per slot time + platform)."""
    rows = []
    for item in weekly_schedule(start):
        existing = (await session.execute(select(SocialPostDraft).where(
            SocialPostDraft.scheduled_for == item["scheduled_for"], SocialPostDraft.platform == item["platform"]
        ))).scalars().first()
        if existing is not None:
            rows.append(existing)
            continue
        post = SocialPostDraft(platform=item["platform"], plan_key=item["plan_key"], theme=item["theme"],
                               text=item["text"], hashtags=item["hashtags"], scheduled_for=item["scheduled_for"],
                               status="draft")
        session.add(post)
        rows.append(post)
    await session.flush()
    return rows


def post_to_dict(p: SocialPostDraft) -> dict:
    return {"id": str(p.id), "platform": p.platform, "plan_key": p.plan_key, "theme": p.theme, "text": p.text,
            "hashtags": p.hashtags or [], "status": p.status,
            "scheduled_for": p.scheduled_for.isoformat() if p.scheduled_for else None}
