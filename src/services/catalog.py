from __future__ import annotations

# =====================================================================
#  Al-Narjis AI — Client Catalog
#  - Employee identity (number + job title) for every agent
#  - Package -> team mapping (dormant set)
#  - Onboarding interview questions per agent (fed into its prompt)
# =====================================================================

# ---------------------------------------------------------------------
#  Domains: the four historical specialist teams (five agents each; a
#  domain team is a staffing template, not what a subscription includes).
#  They describe *what* a team works on and drive lead segmentation,
#  outreach copy and demo content. They carry no price of their own:
#  every price lives in PACKAGES below.
# ---------------------------------------------------------------------
DOMAINS = {
    "social": {
        "name": "سوشيال ميديا",
        "name_en": "Social Media",
        "tagline": "حضور قوي ومحتوى متجدد على منصاتك",
        "tagline_en": "Strong presence and fresh content on your platforms",
    },
    "ecommerce": {
        "name": "متاجر إلكترونية",
        "name_en": "E-commerce",
        "tagline": "متجر ينمّي مبيعاتك ويخدم عملاءك",
        "tagline_en": "A store that grows your sales and serves your customers",
    },
    "content": {
        "name": "تسويق محتوى",
        "name_en": "Content Marketing",
        "tagline": "محتوى يصنع قيمة ويثق جمهورك",
        "tagline_en": "Content that creates value and earns trust",
    },
    "growth": {
        "name": "نمو الأعمال",
        "name_en": "Business Growth",
        "tagline": "خطط وأدوات تنقل عملك لمرحلة جديدة",
        "tagline_en": "Plans and tools that take your business further",
    },
}

DOMAIN_TEAMS = {
    "social": ["social_media", "ad_writer", "content_ideas", "marketing_agent", "text_improver"],
    "ecommerce": ["product_describer", "store_manager", "customer_service", "customer_manager", "email_writer"],
    "content": ["content_writer", "article_writer", "content_manager", "market_analyst", "competitor_analyst"],
    "growth": ["business_ideas", "project_manager", "time_manager", "data_analyst", "cv_writer"],
}

# The CEO agent leads every plan: it diagnoses, then staffs the plan.
CEO_SLUG = "orchestrator"

# ---------------------------------------------------------------------
#  Subscription tiers (pricing v2, Oct 2026). Monthly, SAR, VAT 15% added on
#  top at checkout. ``amount`` is halalas (pre-VAT monthly base) and is the
#  only number payments read; ``price`` is its display form. ``agents`` is
#  the number of specialist agents the CEO can staff on the plan (the CEO
#  itself is always included and is not counted). The price per agent falls
#  as the plan grows: 300 -> 250 -> 233 SAR.
#
#  ``limits`` are the monthly usage allowances of the plan:
#    conversations   - smart conversations (one customer, 24h window, any
#                      number of messages, answered by an AI agent)
#    voice_minutes   - voice-agent minutes
#    meta_cap        - Meta (WhatsApp) conversation fees we cover, halalas;
#                      anything above is passed through at cost.
#  ``setup_fee`` is a one-time fee (halalas) charged on the first monthly
#  order only; it is waived for annual billing and for founding customers.
# ---------------------------------------------------------------------
PACKAGES = {
    "radd": {
        "name": "ردّ",
        "name_en": "Reply",
        "amount": 59900,
        "price": "599",
        "agents": 2,
        "setup_fee": 0,
        "limits": {"conversations": 1000, "voice_minutes": 0, "meta_cap": 10000},
        "tagline": "ما يضيع عليك ولا عميل يسأل — ردّ بلهجتنا خلال ثوانٍ، ليل نهار",
        "tagline_en": "Never miss a customer question — replies in Saudi dialect within seconds, day and night",
        "scope": [
            "وكيلان: ردود ذكية + متابعة الطلب حتى الفاتورة",
            "قناة واتساب",
            "وضع المراجعة: كل ردّ مسودة تعتمدها حتى تقرّر التشغيل التلقائي",
            "فواتير ضريبية ورابط دفع بالبطاقة",
            "١٬٠٠٠ محادثة ذكية شهرياً، ورسوم ميتا مشمولة حتى ١٠٠ ريال",
        ],
        "coming": ["قناة ثانية: تيليجرام أو ماسنجر"],
        "scope_en": [
            "2 agents: smart replies + order follow-up through to the invoice",
            "WhatsApp channel",
            "Review mode: every reply is a draft you approve until you switch on auto-reply",
            "Tax invoices and a card payment link",
            "1,000 smart conversations a month, Meta fees covered up to 100 SAR",
        ],
        "coming_en": ["A second channel: Telegram or Messenger"],
    },
    "bay": {
        "name": "بيع",
        "name_en": "Sell",
        "amount": 149900,
        "price": "1499",
        "agents": 6,
        "setup_fee": 99000,
        "limits": {"conversations": 4000, "voice_minutes": 150, "meta_cap": 25000},
        "tagline": "من أول سؤال حتى يصلك المبلغ — والمتابعة تمشي بدون ما تلاحق أحد",
        "tagline_en": "From the first question to money in your account — follow-ups run without you chasing",
        "scope": [
            "كل ما في ردّ",
            "٦ وكلاء: متابعة مبيعات، ووكيل سوشال بجدول نشر",
            "٤٬٠٠٠ محادثة ذكية، ورسوم ميتا مشمولة حتى ٢٥٠ ريال",
            "ربط متجرك على سلة أو زد (قريباً): الطلبات، تذكير السلات المتروكة، وحالة الشحن",
        ],
        "coming": [
            "وكيل صوتي بلهجة سعودية (١٥٠ دقيقة شهرياً عند الإطلاق)",
            "قنوات إضافية: تيليجرام وماسنجر",
        ],
        "scope_en": [
            "Everything in Reply",
            "6 agents: sales follow-up and a social agent with a posting schedule",
            "4,000 smart conversations, Meta fees covered up to 250 SAR",
            "Connect your Salla or Zid store (coming soon): orders, abandoned-cart reminders and shipping status",
        ],
        "coming_en": [
            "Saudi-dialect voice agent (150 minutes a month at launch)",
            "Extra channels: Telegram and Messenger",
        ],
    },
    "tashgheel": {
        "name": "تشغيل",
        "name_en": "Operate",
        "amount": 349900,
        "price": "3499",
        "agents": 15,
        "setup_fee": 199000,
        "limits": {"conversations": 8000, "voice_minutes": 500, "meta_cap": 50000},
        "tagline": "المبيعات والسوشال تشتغل عنك — وأنت تعتمد القرارات فقط",
        "tagline_en": "Sales and social run for you — you only approve the decisions",
        "scope": [
            "كل ما في بيع",
            "١٥ وكيلاً من أي قسم",
            "تقرير أسبوعي لكل مشروع يراجعه فريقنا قبل إرساله، ومدير حساب",
            "كل القنوات المتاحة حالياً",
            "٨٬٠٠٠ محادثة ذكية، ورسوم ميتا مشمولة حتى ٥٠٠ ريال",
        ],
        "coming": ["خط صوتي (٥٠٠ دقيقة شهرياً عند الإطلاق)", "ربط سلة أو زد (قريباً)", "تيليجرام وماسنجر"],
        "scope_en": [
            "Everything in Sell",
            "15 agents from any department",
            "A weekly report per project, reviewed by our team before it is sent, and an account manager",
            "Every channel available today",
            "8,000 smart conversations, Meta fees covered up to 500 SAR",
        ],
        "coming_en": ["Voice line (500 minutes a month at launch)", "Salla or Zid store connection (coming soon)", "Telegram and Messenger"],
    },
}

PACKAGE_ORDER = ["radd", "bay", "tashgheel"]
RECOMMENDED_PACKAGE = "bay"

# Enterprise is sold by quote only: it is shown on the pricing pages but is
# never a checkout key (payments only accept PACKAGES).
ENTERPRISE = {
    "key": "enterprise",
    "name": "مؤسسات",
    "name_en": "Enterprise",
    "price_from": "6000",
    "amount_from": 600000,
    "by_quote": True,
    "tagline": "أكثر من ١٥ وكيلاً، أو أكثر من رقم وفرع، أو متطلبات أمنية وعقد خاص",
    "tagline_en": "More than 15 agents, several numbers or branches, or security and contract requirements",
    "scope": [
        "عرض سعر حسب الحاجة — يبدأ من ٦٬٠٠٠ ريال شهرياً تقريباً",
        "أكثر من ١٥ وكيلاً وأكثر من رقم وفرع",
        "متطلبات أمنية وعقد خاص واستضافة وشروط بيانات خاصة",
    ],
    "scope_en": [
        "Quoted to your needs — from about 6,000 SAR a month",
        "More than 15 agents, several numbers and branches",
        "Security requirements, a custom contract, hosting and data terms",
    ],
}

# ---------------------------------------------------------------------
#  Add-ons (monthly, pre-VAT, halalas). The extra agent is priced above the
#  per-agent price inside the larger plans so upgrading stays worthwhile;
#  the CEO suggests a tier plus add-on agents only when that is cheaper than
#  the next tier (see ceo_advisor.recommend_offer).
# ---------------------------------------------------------------------
ADDON_AGENT = {
    "name": "وكيل إضافي",
    "name_en": "Add-on agent",
    "amount": 29900,
    "price": "299",
}
MAX_ADDON_AGENTS = 12      # checkout cap per order
MAX_SUGGESTED_ADDONS = 2   # "slightly exceeds": the CEO never suggests more below the top tier

USAGE_ADDONS = {
    "conversations": {
        "name": "١٬٠٠٠ محادثة إضافية",
        "name_en": "+1,000 conversations",
        "amount": 9900,
        "price": "99",
        "units": 1000,
        "note": "رسوم ميتا لا تدخل فيها وتُحسب بالتكلفة",
        "note_en": "Meta fees not included; passed through at cost",
    },
    "voice_minutes": {
        "name": "١٠٠ دقيقة صوت إضافية (قريباً)",
        "name_en": "+100 voice minutes (coming soon)",
        "amount": 9900,
        "price": "99",
        "units": 100,
        # Not sold until the voice agent launches: checkout and the payments
        # API refuse new voice packs while this is False.
        "purchasable": False,
        "note": "",
        "note_en": "",
    },
    "meta_overage": {
        "name": "رسوم ميتا فوق السقف",
        "name_en": "Meta fees above the cap",
        "amount": None,
        "price": None,
        "at_cost": True,
        "note": "بالتكلفة بدون أي زيادة، وتظهر بشفافية في البوابة",
        "note_en": "Passed through at cost with no markup, shown transparently in the portal",
    },
}

# Usage alert thresholds: the owner is alerted once per window at 80% and at
# 100% of any limit. Going over never cuts service: the excess is recorded as
# overage for add-on billing (services.usage).
USAGE_ALERT_RATIO = 0.8
USAGE_ALERT_THRESHOLDS = (80, 100)
MAX_USAGE_PACKS = 20  # checkout cap per pack type per order

# Meta (WhatsApp Cloud API) per-message fees we cover up to ``meta_cap``,
# halalas per billable message by pricing category. ESTIMATES for Saudi
# Arabia (Meta publishes USD rates; reconcile against the Meta invoice).
# Service (customer-initiated) conversations are free.
META_FEE_RATES = {
    "marketing": 17,
    "utility": 4,
    "authentication": 4,
    "authentication_international": 4,
    "service": 0,
}

# ---------------------------------------------------------------------
#  Billing periods. Annual = pay for 10 months, get 12 (2 months free).
#  ``months_billed`` multiplies the monthly base; ``months_granted`` is the
#  access period one paid invoice buys.
# ---------------------------------------------------------------------
BILLING_PERIODS = {
    "monthly": {"months_billed": 1, "months_granted": 1, "label": "شهري", "label_en": "Monthly"},
    "annual": {"months_billed": 10, "months_granted": 12, "label": "سنوي", "label_en": "Annual"},
}
DEFAULT_BILLING_PERIOD = "monthly"

# ---------------------------------------------------------------------
#  Launch policies (approved Oct 2026).
# ---------------------------------------------------------------------
# Founding customers: the first 15. 30% off annual (locked 12 months) or 20%
# off monthly with a 3-month commitment; setup fee waived. In exchange the
# customer agrees to a case study / testimonial after 60 days. Auto-applied at
# checkout to new orders while seats remain (services.founding); the price
# holds for ``locked_months`` from activation, the owner can revoke a seat.
# Removed by the owner on 14 Oct 2026: the founding offer is OFF. Kept as a
# switch (env FOUNDING_ENABLED, default false) so historical rows still read
# correctly; nothing auto-applies a founding discount while it is off.
def founding_enabled() -> bool:
    import os

    return os.getenv("FOUNDING_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")


FOUNDING_OFFER = {
    "seats": 15,
    "annual_pct": 30,
    "monthly_pct": 20,
    "monthly_commitment_months": 3,
    "locked_months": 12,
    "waives_setup_fee": True,
    "requires_testimonial": True,
}

# Setup guarantee: covers the setup fee only. The subscription itself stays
# non-refundable after activation (see the refund policy).
SETUP_GUARANTEE = {
    "business_days": 10,
    "refunds": "setup_fee",
    "text": "إذا لم يعمل أول وكيل على قناتك خلال ١٠ أيام عمل من استلامنا للمتطلبات، نعيد لك رسوم الإعداد كاملة. الضمان على رسوم الإعداد فقط؛ الاشتراك غير قابل للاسترداد بعد التفعيل.",
    "text_en": "If your first agent is not working on your channel within 10 business days of us receiving your requirements, we refund the setup fee in full. The guarantee covers the setup fee only; the subscription is non-refundable after activation.",
}

# Existing subscribers keep their old price at renewal (grandfathering): a
# renewal of a legacy tier is priced from LEGACY_TIERS, not PACKAGES.
GRANDFATHER_RENEWALS = True


def resolve_billing_period(period: str | None) -> str:
    period = (period or "").strip().lower()
    return period if period in BILLING_PERIODS else DEFAULT_BILLING_PERIOD


# Tiers sold before pricing v2. They can no longer be bought, but existing
# subscribers renew on them at their original price (grandfathered), with
# add-on agents at the original 499 SAR.
LEGACY_ADDON_AMOUNT = 49900
LEGACY_TIERS = {
    "starter": {"name": "انطلاقة", "name_en": "Starter", "amount": 49900, "price": "499", "agents": 1, "legacy": True},
    "team": {"name": "فريق", "name_en": "Team", "amount": 149900, "price": "1499", "agents": 3, "legacy": True},
    "scale": {"name": "توسّع", "name_en": "Scale", "amount": 299900, "price": "2999", "agents": 6, "legacy": True},
    "company": {"name": "الشركة الكاملة", "name_en": "Full Company", "amount": 599900, "price": "5999", "agents": 12, "legacy": True},
}


def is_legacy_tier(key: str | None) -> bool:
    return (key or "") in LEGACY_TIERS


def plan_amount(package_key: str, billing_period: str = "monthly", addons: int = 0) -> int:
    """Pre-VAT halalas for one billing period of a tier plus add-on agents.

    Legacy tiers price at their grandfathered amount and add-on rate.
    """
    if package_key in PACKAGES:
        pkg, addon_amount = PACKAGES[package_key], ADDON_AGENT["amount"]
    else:
        pkg, addon_amount = LEGACY_TIERS[package_key], LEGACY_ADDON_AMOUNT
    addons = max(0, int(addons or 0))
    monthly = pkg["amount"] + addons * addon_amount
    return monthly * BILLING_PERIODS[resolve_billing_period(billing_period)]["months_billed"]


def setup_fee(package_key: str, billing_period: str = "monthly", *, renewal: bool = False, founding: bool = False) -> int:
    """One-time setup fee (halalas) for a first order; 0 when waived."""
    if renewal or founding or resolve_billing_period(billing_period) == "annual":
        return 0
    return int(PACKAGES.get(package_key, {}).get("setup_fee", 0) or 0)


def founding_amount(package_key: str, billing_period: str = "monthly", addons: int = 0) -> int:
    """Founding-customer price for one billing period (pre-VAT halalas)."""
    period = resolve_billing_period(billing_period)
    pct = FOUNDING_OFFER["annual_pct"] if period == "annual" else FOUNDING_OFFER["monthly_pct"]
    base = plan_amount(package_key, period, addons)
    return base - (base * pct) // 100


def limits_tier(package_key: str | None) -> str:
    """Pricing-v2 tier whose usage limits apply. Legacy and domain keys map to
    the smallest v2 tier with at least as many agents."""
    tier = resolve_tier(package_key)
    if tier in PACKAGES:
        return tier
    agents = int(LEGACY_TIERS.get(tier, {}).get("agents", 0) or 0)
    for key in PACKAGE_ORDER:
        if PACKAGES[key]["agents"] >= agents:
            return key
    return PACKAGE_ORDER[-1]


def usage_packs_amount(conversation_packs: int = 0, voice_packs: int = 0, billing_period: str = "monthly") -> int:
    """Pre-VAT halalas for usage add-on packs over one billing period."""
    monthly = (max(0, int(conversation_packs or 0)) * USAGE_ADDONS["conversations"]["amount"]
               + max(0, int(voice_packs or 0)) * USAGE_ADDONS["voice_minutes"]["amount"])
    return monthly * BILLING_PERIODS[resolve_billing_period(billing_period)]["months_billed"]


def plan_limits(package_key: str, addon_conversations: int = 0, addon_voice: int = 0) -> dict:
    """Monthly usage allowance of a tier plus usage add-on packs."""
    limits = dict(PACKAGES[limits_tier(package_key)]["limits"])
    limits["conversations"] += max(0, int(addon_conversations or 0)) * USAGE_ADDONS["conversations"]["units"]
    limits["voice_minutes"] += max(0, int(addon_voice or 0)) * USAGE_ADDONS["voice_minutes"]["units"]
    return limits


# Payments recorded before the CEO-advisor rebrand used the four domain keys
# with their own prices, and pricing v2 retired the four agent-count tiers.
# They stay readable (invoices, activation, renewals) but cannot be bought:
# checkout only accepts PACKAGES.
LEGACY_PACKAGES = {
    "social": {**DOMAINS["social"], "amount": 150000, "price": "1500", "legacy": True},
    "ecommerce": {**DOMAINS["ecommerce"], "amount": 100000, "price": "1000", "legacy": True},
    "content": {**DOMAINS["content"], "amount": 120000, "price": "1200", "legacy": True},
    "growth": {**DOMAINS["growth"], "amount": 80000, "price": "800", "legacy": True},
    **LEGACY_TIERS,
}

# A five-agent domain team needs a tier that staffs five agents: Sell (6).
DOMAIN_TIER = {key: "bay" for key in DOMAINS}

# Tier -> member agents. Filled after EMPLOYEES is defined (see bottom).
PACKAGE_TEAMS: dict[str, list[str]] = {}

# Welcoming intro text per agent (what the employee does)
_EMPTY = object()

def _q(key: str, ar: str, en: str) -> dict:
    return {"key": key, "q_ar": ar, "q_en": en}


EMPLOYEES: dict[str, dict] = {
    "social_media": {
        "no": "AG-001",
        "title_ar": "مدير حسابات السوشيال ميديا",
        "title_en": "Social Media Manager",
        "dept": "التسويق الرقمي",
        "intro_ar": "أنا مدير حسابات التواصل الاجتماعي. أساعدك على بناء حضور قوي: أقيّم حسابك الحالي وأبني لك خطة محتوى ونمو واضحة خلال ٣٠ يوماً.",
        "intro_en": "I manage your social accounts. I audit your current presence and build a clear 30-day content and growth plan.",
        "questions": [
            _q("platform", "ما المنصة التي تركز عليها حالياً؟ (مثلاً: إنستغرام، تيك توك، X)", "Which platform do you focus on? (e.g. Instagram, TikTok, X)"),
            _q("followers", "كم عدد المتابعين الحاليين تقريباً؟", "How many followers do you currently have?"),
            _q("engagement", "ما نسبة التفاعل تقريباً؟ (إن لم تعرف، اكتب 'غير معروف')", "What is your approximate engagement rate? (if unknown, write 'unknown')"),
            _q("content_types", "ما نوع المحتوى الذي تنشره حالياً؟ (صور، فيديو، قصص...)", "What types of content do you post? (photos, video, stories...)"),
            _q("frequency", "كم مرة تنشر أسبوعياً؟", "How often do you post per week?"),
            _q("audience", "من هو جمهورك المستهدف؟", "Who is your target audience?"),
            _q("goals", "ما أهدافك من السوشيال ميديا؟ (مبيعات، وعي، تفاعل...)", "What are your social media goals? (sales, awareness, engagement...)"),
            _q("competitors", "من هم منافسوك الرئيسيون؟", "Who are your main competitors?"),
        ],
    },
    "ad_writer": {
        "no": "AG-002",
        "title_ar": "كاتب إعلانات",
        "title_en": "Ad Copywriter",
        "dept": "التسويق الرقمي",
        "intro_ar": "أنا كاتب إعلانات محترف. أكتب لك نصوصاً إعلانية مقنعة تناسب الجمهور والمنصة وتحقق أعلى تفاعل.",
        "intro_en": "I'm a professional ad copywriter. I write persuasive ad copy that fits your audience and platform for maximum results.",
        "questions": [
            _q("product_name", "ما اسم المنتج أو الخدمة التي تعلن عنها؟", "What product or service are you advertising?"),
            _q("platform", "على أي منصة سيعرض الإعلان؟ (إنستغرام، فيسبوك، تيك توك، جوجل...)", "Which platform will the ad run on? (Instagram, Facebook, TikTok, Google...)"),
            _q("audience", "من هو الجمهور المستهدف؟", "Who is the target audience?"),
            _q("features", "ما أهم ٣-٥ مزايا للمنتج؟", "What are the top 3-5 product features?"),
            _q("tone", "ما الأسلوب المطلوب؟ (احترافي، حماسي، فكاهي...)", "What tone do you want? (professional, energetic, humorous...)"),
            _q("cta", "ما الإجراء المطلوب من العميل؟ (اشترِ، سجّل، تواصل...)", "What action should the customer take? (buy, sign up, contact...)"),
            _q("duration", "كم مدة الإعلان إذا كان فيديو؟ (بالثواني)", "If it's a video ad, what is the duration in seconds?"),
        ],
    },
    "content_ideas": {
        "no": "AG-003",
        "title_ar": "مولّد أفكار المحتوى",
        "title_en": "Content Ideas Generator",
        "dept": "المحتوى",
        "intro_ar": "أنا مصدر أفكار المحتوى. أقدّم لك بنك أفكار جاهز للمنشورات والإبداعات يناسب مجالك وجمهورك.",
        "intro_en": "I generate content ideas. I give you a bank of ready-to-use post and creative ideas tailored to your field.",
        "questions": [
            _q("business", "ما نشاطك التجاري؟", "What is your business?"),
            _q("industry", "في أي مجال تعمل؟", "Which industry are you in?"),
            _q("audience", "من جمهورك المستهدف؟", "Who is your audience?"),
            _q("platforms", "ما المنصات التي تنشط عليها؟", "Which platforms are you active on?"),
            _q("pillars", "ما أهم محاور المحتوى لديك؟ (مميزات، أسئلة شائعة، قصص نجاح...)", "What are your content pillars? (features, FAQs, success stories...)"),
            _q("trends", "هل هناك اتجاهات حالية تريد الاستفادة منها؟", "Any current trends you want to leverage?"),
        ],
    },
    "marketing_agent": {
        "no": "AG-004",
        "title_ar": "استراتيجي التسويق",
        "title_en": "Marketing Strategist",
        "dept": "التسويق الرقمي",
        "intro_ar": "أنا استراتيجي التسويق. أضع لك خطة تسويقية متكاملة بميزانية وقنوات وأهداف واضحة.",
        "intro_en": "I'm a marketing strategist. I build you a complete marketing plan with clear budget, channels and goals.",
        "questions": [
            _q("store_context", "صف لي عملك/متجرك بإيجاز", "Briefly describe your business/store"),
            _q("goals", "ما أهداف التسويق؟ (مبيعات، عملاء جدد، وعي...)", "What are your marketing goals? (sales, new customers, awareness...)"),
            _q("audience", "من جمهورك المستهدف؟", "Who is your target audience?"),
            _q("channels", "ما القنوات التي تستخدمها أو تريد استخدامها؟", "Which channels do you use or want to use?"),
            _q("budget", "ما ميزانيتك التسويقية الشهرية المبدئية؟", "What is your initial monthly marketing budget?"),
        ],
    },
    "text_improver": {
        "no": "AG-005",
        "title_ar": "محسّن النصوص",
        "title_en": "Text Improver",
        "dept": "المحتوى",
        "intro_ar": "أنا محرر نصوص. أحسّن أي نص تكتبه: أوضح، أقوى، وأكثر تأثيراً من دون فقدان المعنى.",
        "intro_en": "I'm a text editor. I improve any text you write — clearer, stronger and more impactful without losing meaning.",
        "questions": [
            _q("text", "الصق النص الذي تريد تحسينه", "Paste the text you want to improve"),
            _q("reading_level", "ما مستوى القراءة المستهدف؟ (بسيط، متوسط، متقدم)", "What reading level is the text for? (simple, intermediate, advanced)"),
        ],
    },
    "product_describer": {
        "no": "AG-006",
        "title_ar": "كاتب وصف المنتجات",
        "title_en": "Product Descriptions Writer",
        "dept": "التجارة الإلكترونية",
        "intro_ar": "أنا كاتب وصف المنتجات. أكتب لك وصفاً جذاباً ومحسّناً لمحركات البحث يرفع مبيعات متجرك.",
        "intro_en": "I write product descriptions. I craft attractive, SEO-friendly copy that boosts your store sales.",
        "questions": [
            _q("product_name", "ما اسم المنتج؟", "What is the product name?"),
            _q("category", "ما تصنيف المنتج؟", "What is the product category?"),
            _q("features", "ما أهم ميزاته ومواصفاته؟", "What are its key features and specs?"),
            _q("audience", "من الجمهور المستهدف؟", "Who is the target audience?"),
            _q("keywords", "ما الكلمات المفتاحية المطلوبة؟ (للسيو)", "What keywords do you want included? (for SEO)"),
            _q("brand_voice", "ما هي نبرة علامتك التجارية؟ (فاخرة، شبابية...)", "What is your brand voice? (luxury, youthful...)"),
        ],
    },
    "store_manager": {
        "no": "AG-007",
        "title_ar": "مدير المتجر الإلكتروني",
        "title_en": "Store Manager",
        "dept": "التجارة الإلكترونية",
        "intro_ar": "أنا مدير المتجر الإلكتروني. أقيّم متجرك وأقترح تحسينات عملية ترفع المبيعات وتجربة الشراء.",
        "intro_en": "I manage your online store. I audit it and suggest practical improvements to raise sales and the buying experience.",
        "questions": [
            _q("store_data", "صف لي متجرك: اسمه، منتجاته، منصة البيع (سلة، أونست، شوبيفاي...)", "Describe your store: name, products, sales platform (Salla, Ounass, Shopify...)"),
        ],
    },
    "customer_manager": {
        "no": "AG-008",
        "title_ar": "مدير علاقات العملاء",
        "title_en": "Customer Relationship Manager",
        "dept": "خدمة العملاء",
        "intro_ar": "أنا مدير علاقات العملاء. أقرأ محادثاتك مع العملاء وأقترح ردوداً وجدول تفاعل يبني ولاءً حقيقياً.",
        "intro_en": "I manage customer relationships. I read your customer conversations and suggest responses and an engagement plan that builds loyalty.",
        "questions": [
            _q("profile", "من هو عميلك الرئيسي؟ (نوع النشاط، الفئة العمرية...)", "Who is your main customer? (business type, age group...)"),
            _q("history", "ما طبيعة التعاملات السابقة مع هذا العميل؟", "What is the history of interactions with this customer?"),
            _q("messages", "الصق أحدث محادثة أو استفسار من العميل", "Paste the latest conversation or customer inquiry"),
        ],
    },
    "customer_service": {
        "no": "AG-009",
        "title_ar": "موظف خدمة العملاء",
        "title_en": "Customer Service Agent",
        "dept": "خدمة العملاء",
        "intro_ar": "أنا موظف خدمة العملاء. أرد على استفسارات عملائك ورسائلهم باحترافية وسرعة على مدار الساعة.",
        "intro_en": "I'm a customer service agent. I respond to your customers' inquiries and messages professionally around the clock.",
        "questions": [
            _q("customer_message", "الصق رسالة/استفسار العميل", "Paste the customer's message/inquiry"),
            _q("product_name", "ما المنتج أو الخدمة المرتبطة؟", "Which product or service is it about?"),
            _q("context", "هل هناك سياق أو معلومات إضافية؟", "Any additional context or information?"),
            _q("order_id", "رقم الطلب إن وجد", "Order number if available"),
            _q("order_status", "حالة الطلب إن وجدت", "Order status if available"),
        ],
    },
    "email_writer": {
        "no": "AG-010",
        "title_ar": "كاتب الرسائل الإلكترونية",
        "title_en": "Email Writer",
        "dept": "المحتوى",
        "intro_ar": "أنا كاتب الرسائل الإلكترونية. أكتب لك رسائل واضحة ومقنعة: إعلانات، متابعات، أو رسائل للعملاء.",
        "intro_en": "I write emails. I craft clear, persuasive messages — promos, follow-ups, or customer emails.",
        "questions": [
            _q("purpose", "ما الغرض من الرسالة؟ (إعلان، متابعة، إشعار...)؟", "What is the purpose of the email? (promo, follow-up, notice...)"),
            _q("recipient", "من المستلم؟", "Who is the recipient?"),
            _q("company", "ما اسم الشركة/العلامة؟", "What is the company/brand name?"),
            _q("goal", "ما الهدف المطلوب تحقيقه بعد القراءة؟", "What is the desired outcome after reading?"),
            _q("key_points", "ما النقاط الأساسية التي يجب ذكرها؟", "What key points must be included?"),
            _q("tone", "ما النبرة المطلوبة؟", "What tone should the email have?"),
            _q("cta", "ما الزر/الإجراء المطلوب؟", "What is the call-to-action?"),
        ],
    },
    "content_writer": {
        "no": "AG-011",
        "title_ar": "كاتب المحتوى",
        "title_en": "Content Writer",
        "dept": "المحتوى",
        "intro_ar": "أنا كاتب المحتوى. أكتب لك محتوى مقنعاً وواضحاً بأسلوب يناسب منصتك ويحقّق هدفك.",
        "intro_en": "I'm a content writer. I write persuasive, clear content in a style that fits your platform and goal.",
        "questions": [
            _q("topic", "ما الموضوع؟", "What is the topic?"),
            _q("platform", "ما المنصة؟ (مدونة، إنستغرام، تيك توك...)", "Which platform? (blog, Instagram, TikTok...)"),
            _q("tone", "ما النبرة؟", "What tone?"),
            _q("length", "ما الطول المطلوب تقريباً؟", "What approximate length do you want?"),
        ],
    },
    "article_writer": {
        "no": "AG-012",
        "title_ar": "كاتب المقالات",
        "title_en": "Article Writer",
        "dept": "المحتوى",
        "intro_ar": "أنا كاتب مقالات متخصص. أكتب لك مقالات منظمة ومتعمقة تُثبت خبرتك وتحسّن ظهورك في البحث.",
        "intro_en": "I'm a specialized article writer. I write structured, in-depth articles that build your authority and boost search visibility.",
        "questions": [
            _q("topic", "ما موضوع المقال؟", "What is the article topic?"),
            _q("angle", "ما الزاوية/الرؤية التي تريدها؟", "What angle or angle do you want to take?"),
            _q("audience", "من القراء المستهدفون؟", "Who are the target readers?"),
            _q("key_points", "ما النقاط الرئيسية؟", "What are the key points?"),
            _q("word_count", "كم عدد الكلمات التقريبي؟", "Approximate word count?"),
        ],
    },
    "content_manager": {
        "no": "AG-013",
        "title_ar": "مدير المحتوى",
        "title_en": "Content Manager",
        "dept": "المحتوى",
        "intro_ar": "أنا مدير المحتوى. أبني لك تقويم محتوى منظماً يغطي كل المنصات بالمواعيد والمحاور المطلوبة.",
        "intro_en": "I'm a content manager. I build an organized content calendar covering all platforms with the required pillars and dates.",
        "questions": [
            _q("business", "ما نشاطك التجاري؟", "What is your business?"),
            _q("platforms", "ما المنصات؟", "Which platforms?"),
            _q("pillars", "ما محاور المحتوى؟", "What are your content pillars?"),
            _q("frequency", "كم منشوراً في الأسبوع؟", "How many posts per week?"),
            _q("special_dates", "هل هناك مناسبات أو مواعيد خاصة؟", "Any special dates or occasions?"),
        ],
    },
    "market_analyst": {
        "no": "AG-014",
        "title_ar": "محلل السوق",
        "title_en": "Market Analyst",
        "dept": "التحليلات",
        "intro_ar": "أنا محلل السوق. أدرس قطاعك ومنافسيك والاتجاهات الحالية وأقدم رؤى تدعم قراراتك.",
        "intro_en": "I'm a market analyst. I study your sector, competitors and trends and deliver insights for your decisions.",
        "questions": [
            _q("segment", "ما القطاع/السوق الذي تريد تحليله؟", "Which segment/market do you want analyzed?"),
            _q("competitors", "من هم المنافسون المعنيون؟", "Who are the relevant competitors?"),
            _q("trends", "هل هناك اتجاهات محددة تريد التركيز عليها؟", "Any specific trends to focus on?"),
        ],
    },
    "competitor_analyst": {
        "no": "AG-015",
        "title_ar": "محلل المنافسين",
        "title_en": "Competitor Analyst",
        "dept": "التحليلات",
        "intro_ar": "أنا محلل المنافسين. أفحص منافسيك وأبني لك تقريراً عن نقاط قوتهم وضعفهم وكيف تتفوق عليهم.",
        "intro_en": "I'm a competitor analyst. I examine your competitors and build a report on their strengths, weaknesses and how to outperform them.",
        "questions": [
            _q("our_business", "صف لي عملك بإيجاز", "Briefly describe your business"),
            _q("competitors_data", "اذكر منافسيك: الأسماء، حساباتهم، أو أي بيانات متوفرة", "List your competitors: names, accounts, or any available data"),
        ],
    },
    "business_ideas": {
        "no": "AG-016",
        "title_ar": "مستشار أفكار المشاريع",
        "title_en": "Business Ideas Consultant",
        "dept": "نمو الأعمال",
        "intro_ar": "أنا مستشار أفكار المشاريع. أستكشف مهاراتك واهتماماتك وميزانيتك وأقترح عليك أفكار مشاريع واقعية وقابلة للبدء.",
        "intro_en": "I'm a business ideas consultant. I explore your skills, interests and budget and suggest realistic, startable business ideas.",
        "questions": [
            _q("skills", "ما مهاراتك أو خبراتك؟", "What are your skills or experience?"),
            _q("interests", "ما مجالات اهتمامك؟", "What fields interest you?"),
            _q("budget", "ما رأس المال المتاح للبدء؟", "What startup capital is available?"),
            _q("market", "هل هناك سوق/منطقة تفضّلها؟", "Any preferred market or region?"),
            _q("time", "كم ساعة أسبوعياً تستطيع تخصيصها؟", "How many hours per week can you dedicate?"),
        ],
    },
    "project_manager": {
        "no": "AG-017",
        "title_ar": "مدير المشاريع",
        "title_en": "Project Manager",
        "dept": "نمو الأعمال",
        "intro_ar": "أنا مدير المشاريع. أنظّم مهامك وأولوياتك وجدولك الزمني وأبني خطة تنفيذ واضحة.",
        "intro_en": "I'm a project manager. I organize your tasks, priorities and timeline and build a clear execution plan.",
        "questions": [
            _q("tasks", "ما المهام الرئيسية للمشروع؟", "What are the main project tasks?"),
            _q("timeline", "ما الجدول الزمني التقريبي؟", "What is the approximate timeline?"),
            _q("team_size", "كم عدد أفراد الفريق؟", "How many team members?"),
            _q("priority", "ما أولوية المشروع؟ (عاجل، عادي...)", "What is the project priority? (urgent, normal...)"),
            _q("dependencies", "هل هناك تبعيات أو متطلبات مسبقة؟", "Are there dependencies or prerequisites?"),
        ],
    },
    "time_manager": {
        "no": "AG-018",
        "title_ar": "مدير إدارة الوقت",
        "title_en": "Time Management Coach",
        "dept": "نمو الأعمال",
        "intro_ar": "أنا مدرب إدارة الوقت. أرتب يومك وفق طاقتك ومهامك وأبني لك خطة إنتاجية واقعية.",
        "intro_en": "I'm a time management coach. I organize your day around your energy and tasks and build a realistic productivity plan.",
        "questions": [
            _q("work_hours", "كم ساعة تعمل يومياً؟", "How many hours do you work daily?"),
            _q("tasks", "ما مهامك الأسبوعية الرئيسية؟", "What are your main weekly tasks?"),
            _q("peak_hours", "في أي وقت تكون أكثر إنتاجية؟", "When are you most productive?"),
            _q("meetings", "كم عدد الاجتماعات الأسبوعية؟", "How many meetings per week?"),
            _q("breaks", "كم استراحة خلال اليوم؟", "How many breaks during the day?"),
        ],
    },
    "data_analyst": {
        "no": "AG-019",
        "title_ar": "محلل البيانات",
        "title_en": "Data Analyst",
        "dept": "التحليلات",
        "intro_ar": "أنا محلل البيانات. أقرأ بياناتك وأجيب على أسئلتك التحليلية بأسلوب واضح وقابل للتنفيذ.",
        "intro_en": "I'm a data analyst. I read your data and answer your analytical questions in a clear, actionable way.",
        "questions": [
            _q("data", "الصق بياناتك (أرقام، جداول، ملاحظات)", "Paste your data (numbers, tables, notes)"),
            _q("questions", "ما الأسئلة التي تريد الإجابة عنها؟", "What questions do you want answered?"),
        ],
    },
    "cv_writer": {
        "no": "AG-020",
        "title_ar": "كاتب السيرة الذاتية",
        "title_en": "CV Writer",
        "dept": "نمو الأعمال",
        "intro_ar": "أنا كاتب سير ذاتية احترافي. أصقل خبراتك وأنجزاتك وأكتب لك سيرة ذاتية تترك أثراً.",
        "intro_en": "I'm a professional CV writer. I polish your experience and accomplishments and write a CV that leaves an impact.",
        "questions": [
            _q("target_role", "ما الوظيفة المستهدفة؟", "What is the target role?"),
            _q("personal_info", "ما الاسم وبيانات الاتصال؟", "Name and contact details?"),
            _q("skills", "ما أبرز مهاراتك؟", "What are your top skills?"),
            _q("experience", "ما خبراتك العملية؟", "What is your work experience?"),
            _q("education", "ما مؤهلاتك العلمية؟", "What is your education?"),
            _q("projects", "هل لديك مشاريع أو إنجازات بارزة؟", "Any notable projects or achievements?"),
        ],
    },
    "software_engineer": {
        "no": "AG-021",
        "title_ar": "مهندس البرمجيات",
        "title_en": "Software Engineer",
        "dept": "المنتجات والهندسة",
        "intro_ar": "أنا مهندس البرمجيات. أحوّل فكرتك إلى كود نظيف وعملي: أبني، أصلح، وأحسّن الأنظمة خطوة بخطوة بلغة تفهمها.",
        "intro_en": "I'm a software engineer. I turn your idea into clean, working code — I build, fix and improve systems step by step in your language.",
        "questions": [
            _q("task", "ما الذي تريد بناءه أو إصلاحه؟", "What needs to be built or fixed?"),
            _q("repo_or_code", "الصق رابط المستودع أو الكود الحالي", "Paste the repository link or the existing code"),
            _q("stack", "ما لغة البرمجة والإطار وبيئة التشغيل؟", "Which language, framework, and runtime?"),
        ],
    },
    "orchestrator": {
        "no": "AG-022",
        "title_ar": "الرئيس التنفيذي الافتراضي",
        "title_en": "Virtual CEO",
        "dept": "الإدارة التنفيذية",
        "intro_ar": "أنا الرئيس التنفيذي الافتراضي. أعمل مستشاراً تنفيذياً خاصاً لمالك المشروع: تقارير دورية، تحليلات يومية، ونصائح استراتيجية مبنية على الأرقام.",
        "intro_en": "I'm your virtual Chief Executive. I act as a private executive advisor to the owner — periodic reports, daily analytics, and strategic advice built on numbers.",
        "questions": [
            _q("goal", "ما الهدف الذي تريد قياس تقدمه هذه الفترة؟", "What objective do you want measured this period?"),
            _q("period", "ما الفترة التي تريد تقريراً عنها؟", "Which period should the report cover?"),
            _q("directive", "هل لديك توجيه أو سؤال استراتيجي لي؟", "Do you have a directive or strategic question for me?"),
        ],
    },
    "policy_guardian": {
        "no": "AG-023",
        "title_ar": "حارس السياسات",
        "title_en": "Policy Guardian",
        "dept": "الإدارة التنفيذية",
        "intro_ar": "أنا حارس السياسات. أفحص كل قرار قبل تنفيذه: أحصر ما يُمنع منعاً باتاً، وما يحتاج موافقة المالك، وكل ما عدا ذلك أسمح به.",
        "intro_en": "I'm the Policy Guardian. Every decision passes through me before it executes — I block what's forbidden, flag what needs owner approval, and allow everything else.",
        "questions": [
            _q("action", "ما الإجراء الذي تريد فحصه؟", "What action do you want reviewed?"),
            _q("amount", "ما المبلغ المعني إن وجد؟", "What amount is at stake, if any?"),
            _q("context", "ما الهدف النهائي من هذا الإجراء؟", "What's the end objective of this action?"),
        ],
    },
    "quality_gate": {
        "no": "AG-024",
        "title_ar": "بوابة الجودة",
        "title_en": "Quality Gate",
        "dept": "الإدارة التنفيذية",
        "intro_ar": "أنا بوابة الجودة. لا يصل العميل شيء لا يمر عليّ: أتحقق من الاكتمال والحقائق واللغة والصوت وقابلية التنفيذ، وأعيد ما لا يستحق.",
        "intro_en": "I'm the Quality Gate. Nothing reaches the client without passing me — I check completion, facts, language, voice, and actionability, and send back what isn't ready.",
        "questions": [
            _q("deliverable", "ما المخرجات التي تريد مراجعتها؟", "What deliverable do you want reviewed?"),
            _q("objective", "ما الهدف الأصلي من العمل؟", "What was the original objective?"),
            _q("audience", "لمن هذه المخرجات ولأي غرض؟", "Who is it for and what is it used for?"),
        ],
    },
    "prototype_engineer": {
        "no": "AG-025",
        "title_ar": "مهندس النماذج الأولية",
        "title_en": "Prototype Engineer",
        "dept": "المنتجات والهندسة",
        "intro_ar": "أنا مهندس النماذج الأولية. أحوّل فكرتك إلى منتج رقمي ملموس: شاشات، تجربة مستخدم، وخطة بناء واضحة بالمواصفات.",
        "intro_en": "I'm the Prototype Engineer. I turn your idea into a concrete digital product — screens, user experience, and a clear build plan with specs.",
        "questions": [
            _q("idea", "صف فكرتك بكلماتك", "Describe your idea in your own words"),
            _q("users", "لمن هذا المنتج؟", "Who is this for?"),
            _q("platform", "ما المنصة المستهدفة؟ (ويب، iOS، أندرويد)", "Which platform? (web, iOS, Android)"),
        ],
    },
    "product_designer": {
        "no": "AG-026",
        "title_ar": "مصمم المنتجات",
        "title_en": "Product Designer",
        "dept": "المنتجات والهندسة",
        "intro_ar": "أنا مصمم منتجات. أصنع واجهات وهويات بصرية أنيقة تليق بعلامتك: ألوان، خطوط، ومنظومة مرئية متكاملة.",
        "intro_en": "I'm the Product Designer. I craft elegant, attractive interfaces and visual identities for your brand — colors, typography, and a complete visual system.",
        "questions": [
            _q("assets", "هل لديك شعار أو عناصر هوية حالية؟", "Do you have an existing logo or brand assets?"),
            _q("style", "ما الاتجاه البصري الذي تحبه؟", "What visual direction do you prefer?"),
            _q("surface", "ما الذي نصممه؟ (صفحة، منتج، شاشة تطبيق)", "What are we designing? (page, product, app screen)"),
        ],
    },
    "qa_engineer": {
        "no": "AG-027",
        "title_ar": "مهندس ضمان الجودة",
        "title_en": "QA Engineer",
        "dept": "المنتجات والهندسة",
        "intro_ar": "أنا مهندس ضمان الجودة. أختبر ما يُبنى قبل إطلاقه: حالات اختبار تغطي المسار الطبيعي والحواف والأخطاء الشائعة، مع قرار نهائي بالإطلاق أو التأجيل.",
        "intro_en": "I'm the QA Engineer. I test what gets built before it ships — test cases for the happy path, boundaries, and real-user mistakes — with a clear ship / do-not-ship call.",
        "questions": [
            _q("objective", "ما الذي يجب أن يفعله النظام؟", "What is the system supposed to do?"),
            _q("artifact", "الصق الكود أو السلوك المراد اختباره", "Paste the code or behaviour to test"),
            _q("environment", "ما بيئة التشغيل؟", "What's the environment?"),
        ],
    },
    "integrations_engineer": {
        "no": "AG-028",
        "title_ar": "مهندس التكاملات",
        "title_en": "Integrations Engineer",
        "dept": "المنتجات والهندسة",
        "intro_ar": "أنا مهندس التكاملات. أربط شركتك بالأنظمة التي تعمل عليها أصلاً: المتجر، البريد، الدفع، التقويم، والتحليلات — بأقل صلاحيات وبأمان كامل.",
        "intro_en": "I'm the Integrations Engineer. I connect your business to the systems you already run — store, mail, payments, calendar, analytics — with least-privilege access and full security.",
        "questions": [
            _q("system", "ما النظام الذي تريد الربط معه؟", "Which system do you want to connect?"),
            _q("goal", "ما الهدف من هذا التكامل؟", "What's the goal of this integration?"),
            _q("trigger", "كيف تريد تشغيله؟ (حدث، جدولة، ملف)", "How should it trigger? (event, schedule, file)"),
        ],
    },
    "sales_closer": {
        "no": "AG-029",
        "title_ar": "مسؤول إقناع المبيعات",
        "title_en": "Sales Closer",
        "dept": "التسويق الرقمي",
        "intro_ar": "أنا وكيل مبيعات ذكي. أحوّل الاعتراضات إلى فرص، أبني العروض المناسبة، وأعيد إحياء السلات المتروكة بأسلوب مقنع قائم على القيمة.",
        "intro_en": "I'm a smart sales closer. I turn objections into opportunities, build the right offers, and recover abandoned carts with a persuasive value-driven approach.",
        "questions": [
            _q("message", "ماذا قال العميل في آخر تواصل؟", "What did the customer say last?"),
            _q("catalog", "ما المنتجات والأسعار المتاحة؟", "What products and prices are available?"),
            _q("discount", "ما الحد الأقصى للخصم بدون موافقة؟", "What's the max discount without approval?"),
        ],
    },
    "search_discovery": {
        "no": "AG-030",
        "title_ar": "خبير تحسين البحث SEO",
        "title_en": "SEO Expert",
        "dept": "التسويق الرقمي",
        "intro_ar": "أنا خبير تحسين محركات البحث. أرفع ظهورك في جوجل بخطوات عملية قابلة للتنفيذ: كلمات مفتاحية، أرشفة، وبنية صفحات تسبق المنافسين.",
        "intro_en": "I'm an SEO expert. I raise your visibility on Google with practical, executable steps — keywords, indexing, and page structure that outranks competitors.",
        "questions": [
            _q("url", "ما الموقع أو الصفحة المستهدفة؟", "Which site or page are we working on?"),
            _q("keywords", "ما الكلمات المفتاحية التي تريد المنافسة عليها؟", "What keywords do you want to rank for?"),
            _q("market", "ما السوق واللغة المستهدفة؟", "What market and language?"),
        ],
    },
    "security_compliance": {
        "no": "AG-031",
        "title_ar": "خبير الأمن والامتثال",
        "title_en": "Security & Compliance Expert",
        "dept": "الشؤون المؤسسية",
        "intro_ar": "أنا خبير الأمن والامتثال. أفحص الأنظمة والمواقع والحسابات وأقدم إرشادات أمنية صارمة وواضحة تحمي بياناتك وعملك.",
        "intro_en": "I'm a security & compliance expert. I review systems, sites, stores, and accounts, and give strict, clear security guidance that protects your data and business.",
        "questions": [
            _q("domain", "ما النظام أو المجال الذي نراجعه؟", "What domain or system are we reviewing?"),
            _q("scope", "ما نطاق الفحص؟ (موقع، متجر، حسابات، بنية)", "What's the scope? (site, store, accounts, infrastructure)"),
        ],
    },
    "legal_privacy": {
        "no": "AG-032",
        "title_ar": "مستشار القانون والخصوصية",
        "title_en": "Legal & Privacy Advisor",
        "dept": "الشؤون المؤسسية",
        "intro_ar": "أنا مستشار القانون والخصوصية. أصوّغ مسودات وسياسات وقوائم فحص تجعل مراجعة المحامي قصيرة ورخيصة، وأحدد النقاط التي تحتاج فعلاً محامياً.",
        "intro_en": "I'm the legal & privacy advisor. I draft policies, documents, and checklists that make a lawyer's review short and cheap — and I flag the points that genuinely need one.",
        "questions": [
            _q("doc", "ما الوثيقة التي تحتاجها؟ (سياسة خصوصية، شروط...)", "Which document do you need? (privacy policy, terms...)"),
            _q("jurisdiction", "ما الدول والأنظمة المطبقة عليك؟", "Which jurisdictions apply?"),
            _q("data", "ماذا تفعل الشركة ببيانات العملاء؟", "What does the business do with customer data?"),
        ],
    },
    "finance_pricing": {
        "no": "AG-033",
        "title_ar": "محلل المالية والتسعير",
        "title_en": "Finance & Pricing Analyst",
        "dept": "الشؤون المؤسسية",
        "intro_ar": "أنا محلل المالية والتسعير. الوحيد الذي يرى التكلفة والسعر معاً: أحسب اقتصاديات الوحدة والهوامش وأخبرك أي باقة تخسر مالاً وأيها تربح.",
        "intro_en": "I'm the finance & pricing analyst — the only one who sees cost and price together. I compute unit economics and margins and tell you which package loses money.",
        "questions": [
            _q("costs", "ما التكاليف الشهرية التقريبية؟", "What are your approximate monthly costs?"),
            _q("packages", "ما الباقات وأسعارها الحالية؟", "What packages and prices do you have?"),
            _q("currency", "ما العملات والأسواق المستهدفة؟", "Which currencies and markets?"),
        ],
    },
    "localization": {
        "no": "AG-034",
        "title_ar": "خبير التعريب والتوطين",
        "title_en": "Localization Expert",
        "dept": "المحتوى",
        "intro_ar": "أنا خبير التعريب. لا أترجم — أعَرِّب: أجعل النص يقرأ وكأنه كُتب لسوقك أولاً، بلهجة محلية وعملة وأمثلة تناسب جمهورك.",
        "intro_en": "I'm the Localization Expert. I don't translate — I localize, so text reads as though it was written for your market first, with local idioms, currency, and examples.",
        "questions": [
            _q("text", "الصق النص المراد تعريبه", "Paste the text to localize"),
            _q("target", "إلى أي لغة وسوق؟", "To which language and market?"),
            _q("type", "ما نوع المحتوى؟ (تسويق، منتج، واجهة، قانوني، بريد)", "What type? (marketing, product, UI, legal, email)"),
        ],
    },
    "lead_acquisition": {
        "no": "AG-035",
        "title_ar": "وكيل اكتساب العملاء المحتملين",
        "title_en": "Lead Acquisition Agent",
        "dept": "نمو الأعمال",
        "intro_ar": "أنا وكيل اكتساب العملاء المحتملين. أفلتر الفرع الواردة وأحدّد الأكثر استعداداً للشراء، وأصيغ رسالة تواصل أولى شخصية لكل عميل محتمل — بلهجة سعودية مهنية، بلا مبالغة ولا وعود غير مثبتة.",
        "intro_en": "I'm the Lead Acquisition Agent. I filter inbound leads, rank the ones most ready to buy, and draft a personalized first-contact message for each — professional Saudi tone, no hype and no unproven promises.",
        "questions": [
            _q("source", "من أين تأتي الفرص؟ (موقع، تيليجرام، إحالة، اتصال)", "Where do your leads come from? (site, Telegram, referral, calls)"),
            _q("niche", "ما مجال عملك والجمهور المستهدف؟", "What is your field and target audience?"),
            _q("offer", "ما العرض الذي تقدّمه وسعره؟", "Which offer and price do you present?"),
        ],
    },
}


DEPT_EN: dict[str, str] = {
    "التسويق الرقمي": "Digital Marketing",
    "المحتوى": "Content",
    "نمو الأعمال": "Business Growth",
    "المنتجات والهندسة": "Product & Engineering",
    "التحليلات": "Analytics",
    "الإدارة التنفيذية": "Executive Office",
    "الشؤون المؤسسية": "Corporate Affairs",
    "التجارة الإلكترونية": "E-commerce",
    "خدمة العملاء": "Customer Care",
}


def dept_label(dept: str, lang: str) -> str:
    """Arabic is the source of truth; English pages must never print an Arabic dept."""
    if lang == "en":
        return DEPT_EN.get(dept, dept)
    return dept


_MISSING_DEPT_EN = sorted({e.get("dept", "") for e in EMPLOYEES.values()} - set(DEPT_EN))
if _MISSING_DEPT_EN:
    raise RuntimeError(f"departments without an English label: {_MISSING_DEPT_EN}")

for _employee in EMPLOYEES.values():
    _employee["dept_en"] = DEPT_EN[_employee.get("dept", "")]


DIVISION_SLUGS: dict[str, str] = {
    "الإدارة التنفيذية": "executive-office",
    "نمو الأعمال": "business-growth",
    "التسويق الرقمي": "digital-marketing",
    "المحتوى": "content",
    "التجارة الإلكترونية": "ecommerce",
    "خدمة العملاء": "customer-care",
    "التحليلات": "analytics",
    "المنتجات والهندسة": "product-engineering",
    "الشؤون المؤسسية": "corporate-affairs",
}

DIVISION_BLURBS: dict[str, tuple[str, str]] = {
    "الإدارة التنفيذية": (
        "يقرّر بذكاء ويحوّل الرؤية إلى خطوات أسبوعية",
        "Decides with intelligence and turns vision into weekly moves",
    ),
    "نمو الأعمال": (
        "يبني خط النمو ويقيسه بالمرقام لا بالتخمين",
        "Builds and measures the growth line with numbers, not hunches",
    ),
    "التسويق الرقمي": (
        "يدير حساباتك وإعلاناتك ويجيب الجمهور",
        "Runs your accounts and ads, and answers your audience",
    ),
    "المحتوى": (
        "يبحث ويكتب وينشر بانتظام بلا فراغ",
        "Researches, writes, and publishes on schedule without gaps",
    ),
    "التجارة الإلكترونية": (
        "يرفع التحويل من الزيارة السلة إلى الطلب",
        "Lifts conversion from visit and cart to order",
    ),
    "خدمة العملاء": (
        "يرد على كل رسالة ولا يترك عميلاً ينتظر",
        "Answers every message and leaves no customer waiting",
    ),
    "التحليلات": (
        "يقرأ الأرقام ويخبرك بما يجب تغييره",
        "Reads the numbers and tells you what to change",
    ),
    "المنتجات والهندسة": (
        "يشحن ميزات سريعة بلا أخطاء",
        "Ships fast features without breaking things",
    ),
    "الشؤون المؤسسية": (
        "يرتّب العقود والامتثال والتقارير",
        "Handles contracts, compliance, and reporting",
    ),
}


def build_divisions() -> list[dict]:
    """Derive the division view from EMPLOYEES so the public site can never drift."""
    groups: dict[str, list[str]] = {}
    for slug, employee in EMPLOYEES.items():
        groups.setdefault(employee.get("dept", ""), []).append(slug)

    unknown = sorted(set(groups) - set(DIVISION_SLUGS))
    if unknown:
        raise RuntimeError(f"departments without a division entry: {unknown}")

    divisions: list[dict] = []
    for dept in DIVISION_SLUGS:
        agents = groups.get(dept, [])
        if not agents:
            raise RuntimeError(f"division has no agents: {dept}")
        blurb_ar, blurb_en = DIVISION_BLURBS[dept]
        divisions.append(
            {
                "slug": DIVISION_SLUGS[dept],
                "name_ar": dept,
                "name_en": DEPT_EN[dept],
                "blurb_ar": blurb_ar,
                "blurb_en": blurb_en,
                "count": len(agents),
                "agents": agents,
            }
        )
    return divisions


DIVISIONS: list[dict] = build_divisions()
DIVISION_COUNT: int = len(DIVISIONS)
AGENT_COUNT: int = len(EMPLOYEES)


def get_division(slug: str) -> dict | None:
    for division in DIVISIONS:
        if division["slug"] == slug:
            return division
    return None


def divisions_for_agent(agent_slug: str) -> dict | None:
    employee = EMPLOYEES.get(agent_slug)
    if not employee:
        return None
    return get_division(DIVISION_SLUGS.get(employee.get("dept", ""), ""))


def get_package(package_key: str) -> dict | None:
    """Current tier, or the historical package a stored payment refers to."""
    return PACKAGES.get(package_key) or LEGACY_PACKAGES.get(package_key)


def resolve_tier(key: str | None) -> str:
    """Tier key for a tier, a grandfathered legacy tier or a domain key;
    unknown -> the entry tier."""
    key = (key or "").strip()
    if key in PACKAGES or key in LEGACY_TIERS:
        return key
    return DOMAIN_TIER.get(key, PACKAGE_ORDER[0])


def tier_price_sar(key: str | None) -> int:
    """Pre-VAT monthly price in SAR for a tier or domain key."""
    tier = resolve_tier(key)
    return (PACKAGES.get(tier) or LEGACY_TIERS[tier])["amount"] // 100


def plan_agent_count(key: str) -> int:
    """Specialist agents a tier staffs; the CEO is on top and not counted."""
    agents = (PACKAGES.get(key) or LEGACY_TIERS[key])["agents"]
    return AGENT_COUNT - 1 if agents is None else agents


def addon_quote(package_key: str, addons: int) -> dict:
    """Billing figures for a tier plus ``addons`` extra agents (monthly, pre-VAT)."""
    pkg = PACKAGES.get(package_key) or LEGACY_TIERS[package_key]
    addons = max(0, int(addons or 0))
    return {
        "package": package_key,
        "addons": addons,
        "agents": plan_agent_count(package_key) + addons,
        "tier_halalas": pkg["amount"],
        "addons_halalas": plan_amount(package_key, "monthly", addons) - pkg["amount"],
        "monthly_halalas": plan_amount(package_key, "monthly", addons),
    }


def get_team(package_key: str) -> list[str]:
    return PACKAGE_TEAMS.get(package_key, [])


def get_employee(slug: str) -> dict | None:
    return EMPLOYEES.get(slug)


def employee_identity(slug: str, defn_name: str) -> dict:
    emp = EMPLOYEES.get(slug, {})
    return {
        "no": emp.get("no", "AG-000"),
        "title_ar": emp.get("title_ar", defn_name),
        "title_en": emp.get("title_en", defn_name),
        "dept": emp.get("dept", ""),
        "dept_en": dept_label(emp.get("dept", ""), "en"),
    }


def team_with_identity(agent_slugs: list[str], names: dict[str, str]) -> list[dict]:
    result = []
    for slug in agent_slugs:
        emp = EMPLOYEES.get(slug, {})
        result.append({
            "slug": slug,
            "no": emp.get("no", "AG-000"),
            "title_ar": emp.get("title_ar", names.get(slug, slug)),
            "title_en": emp.get("title_en", names.get(slug, slug)),
            "dept": emp.get("dept", ""),
            "dept_en": dept_label(emp.get("dept", ""), "en"),
            "intro_ar": emp.get("intro_ar", ""),
            "intro_en": emp.get("intro_en", ""),
        })
    return result


def _build_package_teams() -> dict[str, list[str]]:
    growth_first = DOMAIN_TEAMS["growth"] + DOMAIN_TEAMS["social"] + DOMAIN_TEAMS["ecommerce"]
    return {
        "radd": [CEO_SLUG, "customer_service", "customer_manager"],
        "bay": [CEO_SLUG, "customer_service", "customer_manager", "sales_closer",
                "social_media", "store_manager", "marketing_agent"],
        "tashgheel": [CEO_SLUG, *[s for s in ["customer_service", "customer_manager", "sales_closer",
                                             "store_manager", *growth_first] if s != "cv_writer"]],
        # Grandfathered tiers keep their original default teams.
        "starter": [CEO_SLUG, "marketing_agent"],
        "team": [CEO_SLUG, *DOMAIN_TEAMS["social"][:3]],
        "scale": [CEO_SLUG, *DOMAIN_TEAMS["social"], "store_manager"],
        "company": [CEO_SLUG, *[s for s in growth_first if s != "cv_writer"][:12]],
    }


PACKAGE_TEAMS.update(_build_package_teams())
def _dedupe_team(team: list[str], size: int) -> list[str]:
    out: list[str] = []
    for slug in team:
        if slug not in out:
            out.append(slug)
    return out[: size + 1]


for _key in PACKAGES:
    PACKAGE_TEAMS[_key] = _dedupe_team(PACKAGE_TEAMS[_key], PACKAGES[_key]["agents"])
for _key, _pkg in [*PACKAGES.items(), *LEGACY_TIERS.items()]:
    _pkg["agent_count"] = plan_agent_count(_key)
    _pkg["per_agent_price"] = str(round(_pkg["amount"] / 100 / _pkg["agents"]))


# ---------------------------------------------------------------------------
#  Staffing: which agents a project actually gets (tier allowance + add-ons).
# ---------------------------------------------------------------------------

def staffing_pool(package_key: str) -> list[str]:
    """Specialists in the order they are staffed: the tier's own team first,
    then the rest of the roster (domain teams, then everyone else)."""
    tier = resolve_tier(package_key)
    order: list[str] = []
    for slug in [*PACKAGE_TEAMS.get(tier, []), *(s for t in DOMAIN_TEAMS.values() for s in t), *EMPLOYEES]:
        if slug != CEO_SLUG and slug in EMPLOYEES and slug not in order:
            order.append(slug)
    return order


def staff_team(package_key: str, addons: int = 0, preferred: list[str] | None = None) -> list[str]:
    """CEO + exactly ``plan_agent_count(tier) + addons`` specialists.

    ``preferred`` (e.g. the agents the CEO diagnosis recommended) are staffed
    first when they are valid roster slugs; the rest is filled from the tier's
    default team and then the wider roster.
    """
    tier = resolve_tier(package_key)
    allowance = plan_agent_count(tier) + max(0, int(addons or 0))
    chosen: list[str] = []
    for slug in [*(preferred or []), *staffing_pool(tier)]:
        if len(chosen) >= allowance:
            break
        if slug != CEO_SLUG and slug in EMPLOYEES and slug not in chosen:
            chosen.append(slug)
    return [CEO_SLUG, *chosen]
