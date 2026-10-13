"""The CEO advisor: the visitor-facing brain of Al-Narjis.

A visitor describes a business problem in their own words. The CEO agent
(``orchestrator`` in the catalog) diagnoses it, staffs it with the specialist
agents that exist in ``catalog.EMPLOYEES`` and recommends the subscription
tier whose agent allowance covers that team.

Two layers, one contract:

* ``diagnose_rules`` is deterministic keyword matching. It needs no API key,
  makes no network call and is what the tests pin down.
* ``diagnose`` optionally asks the configured LLM chain (the same
  ``ModelProvider.complete_with_fallback`` the consult chat uses) to refine the
  agent choice and the wording. Whatever the model says is validated against
  the catalog; an unknown slug is dropped, and any error or timeout falls back
  to the rules. The plan is always chosen deterministically from the final
  agent count, so the model can never invent a price or a tier.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field

from src.services import catalog, payments

MAX_PROBLEM_CHARS = 2000
MIN_PROBLEM_CHARS = 8
LLM_TIMEOUT_SECONDS = 12.0

# Signal -> agents. Each rule lists Arabic and English stems (lower-cased,
# matched as substrings) and the agents that solve that kind of problem.
@dataclass(frozen=True)
class Need:
    key: str
    label_ar: str
    label_en: str
    stems: tuple[str, ...]
    agents: tuple[str, ...]


NEEDS: tuple[Need, ...] = (
    Need("social", "حضور ضعيف على السوشيال ميديا", "a weak social-media presence",
         ("سوشيال", "انستقرام", "إنستغرام", "انستغرام", "تيك توك", "تيكتوك", "سناب", "متابع", "تفاعل", "منشور",
          "social", "instagram", "tiktok", "snapchat", "followers", "engagement", "posts"),
         ("social_media", "content_ideas")),
    Need("ads", "إعلانات لا تحقق نتائج", "ads that do not convert",
         ("إعلان", "اعلان", "حملة", "حملات", "ads", "campaign", "advert"),
         ("ad_writer", "marketing_agent")),
    Need("marketing", "غياب خطة تسويق واضحة", "no clear marketing plan",
         ("تسويق", "ماركتنق", "خطة تسويق", "عملاء جدد", "وعي", "marketing", "brand", "awareness"),
         ("marketing_agent", "market_analyst")),
    Need("content", "محتوى غير منتظم أو ضعيف", "irregular or weak content",
         ("محتوى", "مقال", "مدونة", "كتابة", "نصوص", "سيو", "content", "article", "blog", "seo", "copy"),
         ("content_writer", "article_writer", "content_manager")),
    Need("store", "متجر إلكتروني مبيعاته أقل من المتوقع", "an online store selling below potential",
         ("متجر", "سلة", "زد", "شوبيفاي", "منتج", "مبيعات المتجر", "سلة متروكة",
          "store", "shop", "salla", "shopify", "product", "cart", "checkout"),
         ("store_manager", "product_describer")),
    Need("support", "ضغط في الرد على العملاء", "customers waiting for replies",
         ("رد", "ردود", "استفسار", "واتساب", "خدمة العملاء", "شكاوى", "شكوى", "رسائل",
          "support", "reply", "replies", "inquir", "complain", "whatsapp", "messages"),
         ("customer_service", "customer_manager")),
    Need("sales", "عملاء محتملون لا يتحولون إلى مبيعات", "leads that do not turn into sales",
         ("مبيعات", "بيع", "صفقات", "عروض أسعار", "عرض سعر", "إغلاق", "عملاء محتمل", "ليدز",
          "sales", "leads", "deal", "close", "quotation", "pipeline"),
         ("sales_closer", "lead_acquisition", "email_writer")),
    Need("analytics", "قرارات بلا أرقام واضحة", "decisions made without clear numbers",
         ("أرقام", "تحليل", "تقارير", "تقرير", "بيانات", "مؤشرات", "data", "analytics", "report", "kpi", "numbers"),
         ("data_analyst", "competitor_analyst")),
    Need("pricing", "تسعير أو هوامش ربح غير واضحة", "unclear pricing or margins",
         ("تسعير", "سعر", "أسعار", "هامش", "ربح", "تكاليف", "pricing", "margin", "profit", "cost"),
         ("finance_pricing",)),
    Need("growth", "نمو متوقف وتحتاج خطة للمرحلة القادمة", "stalled growth that needs a next-stage plan",
         ("نمو", "توسع", "توسّع", "فكرة مشروع", "مشروع جديد", "خطة عمل", "استراتيجية", "منافس",
          "growth", "scale", "expand", "strategy", "startup", "competitor"),
         ("business_ideas", "project_manager", "competitor_analyst")),
    Need("tech", "احتياج تقني: موقع أو تطبيق أو ربط أنظمة", "a technical need: a site, an app or integrations",
         ("موقع", "تطبيق", "برمجة", "ربط", "تكامل", "نظام", "website", "app", "software", "integration", "api"),
         ("software_engineer", "integrations_engineer", "product_designer")),
    Need("legal", "عقود وخصوصية وامتثال", "contracts, privacy and compliance",
         ("عقد", "عقود", "خصوصية", "امتثال", "قانون", "نظام حماية البيانات", "legal", "privacy", "compliance", "contract"),
         ("legal_privacy", "security_compliance")),
    Need("time", "وقت ضائع وفوضى في المهام", "lost time and scattered tasks",
         ("وقت", "مهام", "تنظيم", "فوضى", "متابعة المشاريع", "time", "tasks", "organize", "deadline"),
         ("time_manager", "project_manager")),
    Need("localization", "محتوى بلغتين أو أسواق جديدة", "bilingual content or new markets",
         ("ترجمة", "انجليزي", "إنجليزي", "خليج", "سوق جديد", "translat", "english", "localiz"),
         ("localization",)),
)

# Phrases that ask for the whole company, whatever else they mention.
FULL_COMPANY_STEMS = ("كل شي", "كل شيء", "شركة كاملة", "فريق كامل", "كل الأقسام", "everything", "whole company", "full team")

FALLBACK_AGENT = "marketing_agent"


@dataclass
class Diagnosis:
    needs: list[Need] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    full_company: bool = False
    source: str = "rules"
    summary_ar: str = ""
    summary_en: str = ""


def _normalise(text: str) -> str:
    text = (text or "").strip()[:MAX_PROBLEM_CHARS]
    text = re.sub(r"[\u064B-\u0652\u0640]", "", text)  # tashkeel + tatweel
    return text.lower()


def diagnose_rules(problem: str) -> Diagnosis:
    """Deterministic diagnosis: no key, no network."""
    text = _normalise(problem)
    needs = [n for n in NEEDS if any(stem in text for stem in n.stems)]
    full = any(stem in text for stem in FULL_COMPANY_STEMS)

    agents: list[str] = []
    for need in needs:
        for slug in need.agents:
            if slug in catalog.EMPLOYEES and slug not in agents and slug != catalog.CEO_SLUG:
                agents.append(slug)
    if not agents:
        agents = [FALLBACK_AGENT]
    return Diagnosis(needs=needs, agents=agents, full_company=full)


def recommend_plan(agent_count: int, full_company: bool = False) -> str:
    """Smallest tier whose agent allowance covers the team."""
    if full_company:
        return "company"
    for key in catalog.PACKAGE_ORDER:
        if catalog.plan_agent_count(key) >= agent_count:
            return key
    return "company"


def recommend_offer(agent_count: int, full_company: bool = False) -> tuple[str, int]:
    """(tier, add-on agents) that staffs the team at the lowest monthly price.

    Starts from the smallest covering tier, then checks whether a smaller
    tier plus a few add-on agents (at most ``MAX_SUGGESTED_ADDONS``) is
    strictly cheaper. Beyond the top tier the gap is filled with add-ons.
    """
    if full_company:
        top = catalog.PACKAGE_ORDER[-1]
        return top, max(0, agent_count - catalog.plan_agent_count(top))
    plan = recommend_plan(agent_count)
    top = catalog.PACKAGE_ORDER[-1]
    if catalog.plan_agent_count(plan) < agent_count:
        return top, agent_count - catalog.plan_agent_count(top)
    best, best_addons = plan, 0
    best_price = catalog.plan_amount(plan)
    for key in catalog.PACKAGE_ORDER[: catalog.PACKAGE_ORDER.index(plan)]:
        gap = agent_count - catalog.plan_agent_count(key)
        if 0 < gap <= catalog.MAX_SUGGESTED_ADDONS:
            price = catalog.plan_amount(key, "monthly", gap)
            if price < best_price:
                best, best_addons, best_price = key, gap, price
    return best, best_addons


def _summary(d: Diagnosis) -> tuple[str, str]:
    if d.needs:
        ar_items = "، ".join(n.label_ar for n in d.needs[:4])
        en_items = ", ".join(n.label_en for n in d.needs[:4])
        ar = f"بعد قراءة وصفك، هذه التحديات الأساسية التي أراها: {ar_items}."
        en = f"I diagnosed {len(d.needs)} core challenge{'s' if len(d.needs) != 1 else ''}: {en_items}."
    else:
        ar = "وصفك عام، فأبدأ معك بخطة تسويق واضحة ووكيل واحد، ثم نوسّع الفريق حسب النتائج."
        en = "Your description is broad, so I start with a clear marketing plan and one agent, then grow the team on results."
    if d.full_company:
        ar += " طلبتَ تغطية كل الأقسام، لذلك أرشّح لك الشركة الكاملة."
        en += " You asked for every department, so I recommend the full company."
    return ar, en


def _agent_card(slug: str, need_by_agent: dict[str, Need]) -> dict:
    emp = catalog.EMPLOYEES[slug]
    need = need_by_agent.get(slug)
    return {
        "slug": slug,
        "no": emp.get("no", ""),
        "title_ar": emp.get("title_ar", slug),
        "title_en": emp.get("title_en", slug),
        "dept": emp.get("dept", ""),
        "dept_en": emp.get("dept_en", ""),
        "why_ar": f"لمعالجة: {need.label_ar}" if need else emp.get("intro_ar", "")[:120],
        "why_en": f"To fix: {need.label_en}" if need else emp.get("intro_en", "")[:120],
        "url": f"/ai-agent/{slug}",
    }


def build_result(d: Diagnosis) -> dict:
    plan_key, addons = recommend_offer(len(d.agents), d.full_company)
    pkg = catalog.PACKAGES[plan_key]
    base = catalog.plan_amount(plan_key, "monthly", addons)
    annual_base = catalog.plan_amount(plan_key, "annual", addons)
    vat = payments.vat_amount(base)
    total = payments.total_with_vat(base)

    need_by_agent: dict[str, Need] = {}
    for need in d.needs:
        for slug in need.agents:
            need_by_agent.setdefault(slug, need)

    summary_ar, summary_en = d.summary_ar, d.summary_en
    if not summary_ar or not summary_en:
        summary_ar, summary_en = _summary(d)

    from src.services import transfer

    addon_txt = f" + {addons} وكيل إضافي" if addons else ""
    wa_text = (
        f"مرحباً، أرشّح لي الرئيس التنفيذي في النرجس باقة {pkg['name']}{addon_txt} "
        f"({base // 100} ر.س شهرياً). أريد البدء."
    )
    subscribe = f"/portal?pkg={plan_key}" + (f"&addons={addons}" if addons else "")
    channels = transfer.contact_channels(wa_text)
    ceo = catalog.EMPLOYEES[catalog.CEO_SLUG]
    return {
        "source": d.source,
        "ceo": {"no": ceo["no"], "title_ar": ceo["title_ar"], "title_en": ceo["title_en"]},
        "diagnosis_ar": summary_ar,
        "diagnosis_en": summary_en,
        "needs": [{"key": n.key, "label_ar": n.label_ar, "label_en": n.label_en} for n in d.needs],
        "agents": [_agent_card(s, need_by_agent) for s in d.agents],
        "agent_count": len(d.agents),
        "plan": {
            "key": plan_key,
            "name": pkg["name"],
            "name_en": pkg["name_en"],
            "price": pkg["price"],
            "agents_included": pkg["agent_count"] + addons,
            "tier_agents": pkg["agent_count"],
            "monthly_price": str(base // 100),
            "addons": addons,
            "addon_price": catalog.ADDON_AGENT["price"],
            "addons_halalas": addons * catalog.ADDON_AGENT["amount"],
            "monthly_halalas": base,
            "annual_halalas": annual_base,
            "annual_total_halalas": payments.total_with_vat(annual_base),
            "base_halalas": base,
            "vat_halalas": vat,
            "total_halalas": total,
            "total_sar": f"{total / 100:,.2f}",
            "vat_rate": payments.VAT_RATE,
        },
        "cta": {
            "subscribe": subscribe,
            "telegram": f"{transfer.TELEGRAM_BOT}?start=plan_{plan_key}",
            "whatsapp": channels.get("whatsapp", ""),
        },
    }


def _llm_prompt(problem: str, rules: Diagnosis, locale: str) -> tuple[str, str]:
    roster = "\n".join(
        f"- {slug}: {e['title_en']} / {e['title_ar']} ({e['dept_en']})"
        for slug, e in catalog.EMPLOYEES.items() if slug != catalog.CEO_SLUG
    )
    system = (
        "You are the Virtual CEO of Al-Narjis AI, a Saudi platform of AI agents. "
        "Diagnose the visitor's business problem and staff it with the FEWEST agents "
        "that solve it, chosen ONLY from this roster (use the slug):\n" + roster +
        "\nNever invent numbers, results or prices. Reply with JSON only: "
        '{"diagnosis_ar": "...", "diagnosis_en": "...", "agents": ["slug", ...], "full_company": false}'
    )
    hint = ", ".join(rules.agents)
    prompt = f"Visitor problem ({locale}):\n{problem}\n\nA keyword pre-screen suggested: {hint}\nJSON:"
    return system, prompt


_CLOUD_PROVIDERS = {"openai", "groq", "anthropic", "gemini", "moonshot", "openrouter"}


def _has_cloud_model(provider) -> bool:
    clients = getattr(provider, "_clients", {}) or {}
    return any(getattr(k, "value", str(k)) in _CLOUD_PROVIDERS for k in clients)


async def diagnose(problem: str, *, provider=None, locale: str = "ar") -> dict:
    """Full CEO consultation result. Never raises for model trouble."""
    rules = diagnose_rules(problem)
    final = rules
    if provider is not None and _has_cloud_model(provider):
        try:
            from src.core.model_provider import ModelRequest

            system, prompt = _llm_prompt(problem, rules, locale)
            response = await asyncio.wait_for(
                provider.complete_with_fallback(
                    "gemini", ModelRequest(prompt=prompt, system_prompt=system, temperature=0.2, max_tokens=600)
                ),
                timeout=LLM_TIMEOUT_SECONDS,
            )
            match = re.search(r"\{.*\}", response.content or "", re.S)
            data = json.loads(match.group(0)) if match else {}
            slugs = [
                s for s in dict.fromkeys(data.get("agents") or [])
                if isinstance(s, str) and s in catalog.EMPLOYEES and s != catalog.CEO_SLUG
            ]
            if slugs:
                final = Diagnosis(
                    needs=rules.needs,
                    agents=slugs,
                    full_company=bool(data.get("full_company")) or rules.full_company,
                    source="llm",
                    summary_ar=str(data.get("diagnosis_ar") or "")[:600],
                    summary_en=str(data.get("diagnosis_en") or "")[:600],
                )
        except Exception:  # noqa: BLE001 - any model failure falls back to rules
            final = rules
    return build_result(final)


def validate_problem(problem: str) -> str:
    text = (problem or "").strip()
    if len(text) < MIN_PROBLEM_CHARS:
        raise ValueError("problem too short")
    return text[:MAX_PROBLEM_CHARS]


def whatsapp_link(message: str) -> str:
    from src.services import transfer

    return transfer.contact_channels(message).get("whatsapp", "")


__all__ = ["diagnose", "diagnose_rules", "recommend_plan", "build_result", "validate_problem", "NEEDS"]
