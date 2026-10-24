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

from src.services import catalog, payments, policies

MAX_PROBLEM_CHARS = 2000
MIN_PROBLEM_CHARS = 8
LLM_TIMEOUT_SECONDS = 12.0

# Signal -> agents. Each rule lists Arabic and English stems (lower-cased,
# matched per token, see ``stem_matches``) and the agents that solve that kind of problem.
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
         ("رد", "ردود", "أرد", "نرد", "يرد", "استفسار", "واتساب", "خدمة العملاء", "شكاوى", "شكوى", "رسائل",
          "support", "reply", "replies", "inquir", "complain", "whatsapp", "messages"),
         ("customer_service", "customer_manager")),
    Need("sales", "عملاء محتملون لا يتحولون إلى مبيعات", "leads that do not turn into sales",
         ("مبيعات", "بيع", "نبيع", "أبيع", "يبيع", "صفقات", "عروض أسعار", "عرض سعر", "إغلاق", "عملاء محتمل", "ليدز",
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


# ---------------------------------------------------------------- matching
# Word/token matching instead of raw substrings: "محل ورد" (a flower shop) must
# not trigger the "رد" (reply) need. Each text token is compared with each stem
# token after peeling common Arabic proclitics (ال، و، ف، ب، ل، ك ...). A
# proclitic is only peeled when what is left is still a plausible word, so the
# root letters of "ورد" / "بيع" / "ربح" are never mistaken for a prefix.
_AR_ARTICLE_PREFIXES = ("وال", "فال", "بال", "كال", "لل", "ال")
_AR_SINGLE_PREFIXES = ("و", "ف", "ب", "ل", "ك")
_SHORT_STEM = 3  # stems this short must match a whole token (after prefix peel)


def _fold(text: str) -> str:
    text = _normalise(text)
    text = re.sub("[\u0623\u0625\u0622]", "\u0627", text)  # أ إ آ -> ا
    return text.replace("\u0649", "\u064a").replace("\u0629", "\u0647")  # ى->ي, ة->ه


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\w']+", _fold(text))


def _variants(token: str) -> set[str]:
    out = {token}
    for pre in _AR_ARTICLE_PREFIXES:
        if token.startswith(pre) and len(token) - len(pre) >= 2:
            out.add(token[len(pre):])
    for pre in _AR_SINGLE_PREFIXES:
        rest = token[len(pre):]
        if token.startswith(pre) and len(rest) >= 3:
            out.add(rest)
            for art in ("ال",):
                if rest.startswith(art) and len(rest) - 2 >= 2:
                    out.add(rest[2:])
    return out


def _token_matches(token: str, stem: str) -> bool:
    for v in _variants(token):
        if len(stem) <= _SHORT_STEM:
            if v == stem or (stem.isascii() and v == stem + "s"):
                return True
        elif v.startswith(stem):
            return True
    return False


def stem_matches(tokens: list[str], stem: str) -> bool:
    """True when ``stem`` (one or more words) appears as whole tokens in order."""
    parts = tokenize(stem)
    if not parts:
        return False
    n = len(parts)
    for i in range(len(tokens) - n + 1):
        if all(_token_matches(tokens[i + j], parts[j]) for j in range(n)):
            return True
    return False


def diagnose_rules(problem: str) -> Diagnosis:
    """Deterministic diagnosis: no key, no network."""
    tokens = tokenize(problem)
    needs = [n for n in NEEDS if any(stem_matches(tokens, stem) for stem in n.stems)]
    full = any(stem_matches(tokens, stem) for stem in FULL_COMPANY_STEMS)

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
    top = catalog.PACKAGE_ORDER[-1]
    if full_company:
        return top
    for key in catalog.PACKAGE_ORDER:
        if catalog.plan_agent_count(key) >= agent_count:
            return key
    return top


def recommend_offer(agent_count: int, full_company: bool = False,
                    agents: list[str] | None = None) -> tuple[str, int]:
    """(tier, add-on agents) that staffs the team at the lowest monthly price.

    Without ``agents`` it sizes by count only (legacy contract). With the
    recommended ``agents`` it only accepts an offer that really contains them:
    a tier whose published team (``catalog.PACKAGE_TEAMS``) includes every
    agent, or a smaller tier plus exactly the missing agents as add-ons (at
    most ``MAX_SUGGESTED_ADDONS``). A tier is never recommended just because
    its agent count is large enough.
    """
    top = catalog.PACKAGE_ORDER[-1]
    if full_company:
        return top, max(0, agent_count - catalog.plan_agent_count(top))
    if agents:
        wanted = [a for a in dict.fromkeys(agents) if a != catalog.CEO_SLUG]
        best: tuple[str, int] | None = None
        best_price = None
        for key in catalog.PACKAGE_ORDER:
            team = set(catalog.PACKAGE_TEAMS.get(key, []))
            missing = sum(1 for a in wanted if a not in team)
            addons = max(missing, len(wanted) - catalog.plan_agent_count(key), 0)
            if addons and (key == top or addons <= catalog.MAX_SUGGESTED_ADDONS):
                pass
            elif addons:
                continue
            price = catalog.plan_amount(key, "monthly", addons)
            if best_price is None or price < best_price:
                best, best_price = (key, addons), price
        return best or (top, 0)
    plan = recommend_plan(agent_count)
    if catalog.plan_agent_count(plan) < agent_count:
        return top, agent_count - catalog.plan_agent_count(top)
    best_key, best_addons = plan, 0
    best_amt = catalog.plan_amount(plan)
    for key in catalog.PACKAGE_ORDER[: catalog.PACKAGE_ORDER.index(plan)]:
        gap = agent_count - catalog.plan_agent_count(key)
        if 0 < gap <= catalog.MAX_SUGGESTED_ADDONS:
            price = catalog.plan_amount(key, "monthly", gap)
            if price < best_amt:
                best_key, best_addons, best_amt = key, gap, price
    return best_key, best_addons


def _summary(d: Diagnosis) -> tuple[str, str]:
    if d.needs:
        ar_items = "، ".join(n.label_ar for n in d.needs[:4])
        en_items = ", ".join(n.label_en for n in d.needs[:4])
        ar = f"بعد قراءة وصفك، هذه التحديات الأساسية التي أراها: {ar_items}."
        en = f"I diagnosed {len(d.needs)} core challenge{'s' if len(d.needs) != 1 else ''}: {en_items}."
    elif d.full_company:
        ar = "طلبتَ فريقاً يغطي كل أقسام نشاطك."
        en = "You asked for a team that covers every part of your business."
    else:
        ar = "وصفك عام، فأبدأ معك بخطة تسويق واضحة ووكيل واحد، ثم نوسّع الفريق حسب النتائج."
        en = "Your description is broad, so I start with a clear marketing plan and one agent, then grow the team on results."
    if d.full_company:
        top = catalog.PACKAGES[catalog.PACKAGE_ORDER[-1]]
        ar += f" طلبتَ تغطية كل الأقسام، لذلك أرشّح لك باقة {top['name']}."
        en += f" You asked for every department, so I recommend the {top['name_en']} plan."
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
    plan_key, addons = recommend_offer(len(d.agents), d.full_company, agents=d.agents)
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
    if d.agents:
        subscribe += "&agents=" + ",".join(d.agents)
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
            "vat_rate": payments.vat_rate(),
        },
        "cta": {
            "subscribe": subscribe,
            "telegram": "",
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
        "\nNever invent numbers, results or prices.\n" + policies.POLICY_PROMPT +
        "\nReply with JSON only: "
        '{"diagnosis_ar": "...", "diagnosis_en": "...", "agents": ["slug", ...], "full_company": false}'
    )
    hint = ", ".join(rules.agents)
    prompt = f"Visitor problem ({locale}):\n{problem}\n\nA keyword pre-screen suggested: {hint}\nJSON:"
    return system, prompt


_CLOUD_PROVIDERS = {"openai", "groq", "anthropic", "gemini", "moonshot", "openrouter"}


def _has_cloud_model(provider) -> bool:
    clients = getattr(provider, "_clients", {}) or {}
    return any(getattr(k, "value", str(k)) in _CLOUD_PROVIDERS for k in clients)


_INTERNAL_LEAK = re.compile(r"محمد|Mohammed|تصعيد|escalat", re.I)
_ARABIC = re.compile(r"[\u0600-\u06FF]")


def _safe_summary(text: str, fallback: str, *, arabic: bool) -> str:
    """Model summaries are shown to visitors: drop internal escalation notes and
    an "Arabic" summary that came back in another language."""
    t = (text or "").strip()[:600]
    if not t or _INTERNAL_LEAK.search(t) or (arabic and not _ARABIC.search(t)):
        return fallback
    return t


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
                    summary_ar=_safe_summary(str(data.get("diagnosis_ar") or ""), rules.summary_ar, arabic=True),
                    summary_en=_safe_summary(str(data.get("diagnosis_en") or ""), rules.summary_en, arabic=False),
                )
        except Exception:  # noqa: BLE001 - any model failure falls back to rules
            final = rules
    return public_output_check(build_result(final), problem)


# ------------------------------------------------------- public output check
# The CEO result is shown to anonymous visitors. These deterministic rules run
# after the rules/LLM diagnosis and never call a model. Patterns match the
# folded text (أ/إ/آ->ا, ة->ه, ى->ي, no tashkeel, lower case).
_OUT_OF_SCOPE = re.compile(
    r"(احجز|تحجز|نحجز|حجز|\bbook|\breserve)[^.?!؟]{0,25}(فندق|فنادق|طيران|رحله|تذكره|تذاكر|\bflights?\b|\bhotels?\b|\btickets?\b)|"
    r"رحله طيران|تذكره طيران|تذاكر طيران|تاشيره سفر|plane ticket|\bflights? to\b"
)
_REFUND_OR_COMPLAINT = re.compile(
    r"فلوسي|ابي استرداد|ابغي استرداد|اريد استرداد|استرداد المبلغ|استرجاع المبلغ|رجعوا لي|ارجعوا|"
    r"دفعت لكم|بشتكي|راح اشتكي|بقدم شكوي|"
    r"refund me|my money back|full refund|want (a|my) refund|i paid you|i will complain|file a complaint"
)
_TAX = re.compile(
    r"فاتوره ضريبيه|فواتير ضريبيه|رقم ضريبي|رقمكم الضريبي|زاتكا|هيئه الزكاه|"
    r"(اسعار|سعر|فاتوره|الباقه|الباقات)[^.?!؟]{0,30}ضريب|ضريب[^.?!؟]{0,30}(اسعار|سعر|فاتوره|الباقه|الباقات)|"
    r"tax invoice|vat number|\bzatca\b|(price|invoice|plan)[^.?!]{0,30}\bvat\b|\bvat\b[^.?!]{0,30}(price|invoice|plan)"
)
_PAY_NOW = re.compile(
    r"(ابي|ابغي|اريد|ودي|كيف|وين|ممكن|ابا)[^.?!؟]{0,20}(ادفع|اشترك|اشتري|الدفع)|رابط الدفع|رابط دفع|"
    r"اذا دفعت|ادفع سنوي|كم سعر|كم اسعار|اسعار باقات|اسعار الباقات|اسعاركم|"
    r"\bpay (now|by|for|with|online)|payment link|buy now|\bcheckout|subscribe now|how (do|can) i pay|"
    r"how much|your prices|plan prices|want to (pay|buy|subscribe)"
)
# Never show visitors internal routing, owner names or tax promises.
_PUBLIC_LEAK = re.compile(
    r"محمد|mohammed|تصعيد|escalat|المالك|\bowner\b|حارس السياسات|policy guardian|"
    r"ضريب|zatca|\bvat\b|tax invoice|هيئه الزكاه",
    re.I,
)
_NON_PUBLIC_AGENTS = {"policy_guardian", "finance_pricing"}

HANDOFF_AR = "اضغط «اطلب تواصل موظف» في مساعد النرجس، ويرد عليك الفريق بالبريد."
HANDOFF_EN = "Press \u201cAsk a person\u201d in the Al-Narjis assistant and the team will reply by email."
TAX_AR = "أسعارنا نهائية بدون ضريبة قيمة مضافة، لأن الجهة المشغّلة غير مسجّلة في ضريبة القيمة المضافة؛ لذلك لا نصدر فواتير ضريبية، ونرسل فاتورة دفع عادية."
TAX_EN = "Our prices are final with no VAT, because the operator is not VAT-registered, so we do not issue tax invoices; you get a regular payment invoice."


def _prices_line() -> tuple[str, str]:
    months = catalog.BILLING_PERIODS["annual"]
    ar, en = [], []
    for pkg in catalog.PACKAGES.values():
        fee = pkg["setup_fee"] // 100
        ar.append(f"{pkg['name']} {int(pkg['price']):,} ر.س شهرياً" + (f" + إعداد {fee:,} ر.س مرة واحدة" if fee else " بدون رسوم إعداد"))
        en.append(f"{pkg['name_en']} SAR {int(pkg['price']):,}/month" + (f" + SAR {fee:,} one-time setup" if fee else ", no setup fee"))
    return (
        "الباقات: " + "، ".join(ar) + f". السنوي: تدفع {months['months_billed']} أشهر وتحصل على {months['months_granted']}.",
        "Plans: " + "; ".join(en) + f". Yearly: pay {months['months_billed']} months, get {months['months_granted']}.",
    )


def _no_offer(result: dict, ar: str, en: str, reason: str) -> dict:
    result.update(diagnosis_ar=ar, diagnosis_en=en, needs=[], agents=[], agent_count=0, offer=False, notice=reason)
    result["cta"] = {**result.get("cta", {}), "subscribe": "", "whatsapp": ""}
    return result


def public_output_check(result: dict, problem: str) -> dict:
    """Deterministic last pass over a CEO result before a visitor sees it.

    (a) no internal escalation/owner wording, (b) no tax-invoice/ZATCA/VAT promise,
    (c) pay/buy-now questions get the payments-closed notice and no purchase CTA,
    (d) out-of-scope or refund/complaint requests get no sales offer.
    """
    text = _fold(problem)
    result.setdefault("offer", True)
    result.setdefault("notice", "")
    closed = not payments.payments_open()

    if _OUT_OF_SCOPE.search(text):
        return _no_offer(
            result,
            "هذا الطلب خارج ما نقدمه: النرجس تبني وكلاء ذكاء اصطناعي لأتمتة أعمال الشركات، ولا تحجز فنادق أو رحلات.",
            "This is outside what we do: Al-Narjis builds AI agents that automate business work; we do not book hotels or travel.",
            "out_of_scope",
        )
    if _REFUND_OR_COMPLAINT.search(text):
        return _no_offer(
            result,
            "نعتذر عن تجربتك. الاسترداد الوحيد هو رسوم الإعداد لمرة واحدة إذا لم يعمل أول وكيل خلال 10 أيام عمل. " + HANDOFF_AR,
            "We are sorry about your experience. The only refund is the one-time setup fee if the first agent is not working within 10 business days. " + HANDOFF_EN,
            "refund",
        )
    if _TAX.search(text):
        return _no_offer(result, TAX_AR, TAX_EN, "tax")
    if closed and _PAY_NOW.search(text):
        prices_ar, prices_en = _prices_line()
        return _no_offer(
            result,
            payments.PAYMENTS_CLOSED_AR + " " + prices_ar,
            payments.PAYMENTS_CLOSED_EN + " " + prices_en,
            "payments_closed",
        )

    # (a)/(b) on whatever text is left: fall back to the rule summary wording.
    for key, fb in (("diagnosis_ar", "وصفك يحتاج فريقاً صغيراً نبدأ به ثم نوسّعه حسب النتائج."),
                    ("diagnosis_en", "Your goal needs a small starting team that we grow on results.")):
        if _PUBLIC_LEAK.search(_fold(result.get(key, ""))):
            result[key] = fb
    kept = [a for a in result.get("agents", []) if a.get("slug") not in _NON_PUBLIC_AGENTS]
    if kept:
        result["agents"], result["agent_count"] = kept, len(kept)
    if closed:
        result["notice"] = "payments_closed"
    return result


def validate_problem(problem: str) -> str:
    text = (problem or "").strip()
    if len(text) < MIN_PROBLEM_CHARS:
        raise ValueError("problem too short")
    return text[:MAX_PROBLEM_CHARS]


def whatsapp_link(message: str) -> str:
    from src.services import transfer

    return transfer.contact_channels(message).get("whatsapp", "")


__all__ = ["diagnose", "diagnose_rules", "recommend_plan", "build_result", "validate_problem", "NEEDS"]
