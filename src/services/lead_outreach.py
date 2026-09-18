"""Arabic-first, personalized outreach draft generation.

Templates are deterministic and driven by the lead's real attributes (segment,
relationship, package), so messages are specific rather than generic spam. The
generator never claims the AI already did work for the company — it offers a
personalized demo.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

from src.config.settings import settings
from src.services import catalog
from src.services.lead_normalize import wa_me_number

VARIANT_QUOTE = "quote_followup"
VARIANT_CUSTOMER = "customer_reengage"
VARIANT_COLD = "cold_intro"

VARIANT_LABELS_AR = {
    VARIANT_QUOTE: "متابعة عرض سعر",
    VARIANT_CUSTOMER: "عميل سابق",
    VARIANT_COLD: "تعريف أول",
}

# What the AI team can take over for this segment.
VALUE_BY_SEGMENT_AR = {
    "ecommerce": "وصف المنتجات، الرد على استفسارات العملاء، ومتابعة الطلبات على مدار الساعة",
    "retail": "تجديد العروض والمحتوى أسبوعياً على قنواتك وجذب زيارات لمتجرك",
    "restaurant_food": "منشورات وعروض وأسعار تتجدّد أسبوعياً وتفاعل مع عملائك",
    "beauty": "محتوى تجميل يجذب العميلات وتنظيم المواعيد والردود",
    "real_estate": "وصف العقارات، محتوى تسويقي، ومتابعة العملاء المحتملين",
    "healthcare": "محتوى توعوي، ردود على الاستفسارات، وتنظيم المواعيد",
    "education": "محتوى تعليمي، رسائل لأولياء الأمور، وإعلانات التسجيل",
    "professional_services": "محتوى يبني الثقة وردود احترافية على استفسارات العملاء",
    "services": "عروض ومحتوى وردود سريعة على العملاء بشكل مستمر",
    "other": "إنتاج المحتوى والتسويق ومتابعة العملاء بشكل مستمر",
    "unknown": "إنتاج المحتوى والتسويق ومتابعة العملاء بشكل مستمر",
}

VALUE_BY_SEGMENT_EN = {
    "ecommerce": "product descriptions, customer replies, and order follow-ups around the clock",
    "retail": "weekly offers and content that drive footfall to your store",
    "restaurant_food": "weekly posts, offers and prices, and steady engagement with your customers",
    "beauty": "content that attracts clients plus booking and reply automation",
    "real_estate": "property listings, marketing content, and prospect follow-up",
    "healthcare": "awareness content, inquiry replies, and appointment organization",
    "education": "educational content, parent messages, and enrollment ads",
    "professional_services": "trust-building content and professional client replies",
    "services": "offers, content and fast customer replies on a continuous basis",
    "other": "content production, marketing and customer follow-up on a continuous basis",
    "unknown": "content production, marketing and customer follow-up on a continuous basis",
}


def _val(lead: Any, key: str, default: Any = None) -> Any:
    if isinstance(lead, dict):
        return lead.get(key, default)
    return getattr(lead, key, default)


def determine_variant(lead: Any) -> str:
    if _val(lead, "quotation_without_purchase"):
        return VARIANT_QUOTE
    if _val(lead, "historical_customer"):
        return VARIANT_CUSTOMER
    return VARIANT_COLD


def _package_name(package_key: Optional[str], lang: str) -> str:
    pkg = catalog.PACKAGES.get(package_key or "")
    if not pkg:
        return "النرجس" if lang == "ar" else "Al-Narjis"
    return pkg["name"] if lang == "ar" else pkg["name_en"]


def _package_value(package_key: Optional[str], lang: str) -> str:
    taglines = {
        "social": ("إدارة السوشيال ميديا والمحتوى اليومي", "social media management and daily content"),
        "ecommerce": ("تشغيل المتجر ووصف المنتجات وخدمة العملاء", "store operations, product copy and customer service"),
        "content": ("إنتاج محتوى تسويقي مستمر", "continuous marketing content production"),
        "growth": ("خطط النمو والتحليلات ومتابعة المشاريع", "growth plans, analytics and project follow-up"),
    }
    ar, en = taglines.get(package_key or "", ("فريق وكلاء ذكاء اصطناعي متخصص", "a specialist AI-agent team"))
    return ar if lang == "ar" else en


def generate_message(
    lead: Any,
    *,
    variant: Optional[str] = None,
    lang: str = "ar",
) -> dict:
    """Return ``{variant, message, wa_link, wa_number, package}`` for a lead."""
    variant = variant or determine_variant(lead)
    company = (_val(lead, "company_name") or "").strip()
    contact = (_val(lead, "contact_name") or "").strip()
    segment = _val(lead, "segment") or "unknown"
    package = _val(lead, "suggested_package") or "social"

    greeting_name = contact or company or ("عميلنا العزيز" if lang == "ar" else "there")
    if lang == "en":
        value = VALUE_BY_SEGMENT_EN.get(segment, VALUE_BY_SEGMENT_EN["unknown"])
        pkg = _package_name(package, lang)
        pkg_value = _package_value(package, lang)
        if variant == VARIANT_QUOTE:
            message = (
                f"Hello {greeting_name}, this is the Al-Narjis AI team.\n"
                f"We noticed {company or 'your company'} had requested a quotation earlier.\n"
                f"Our AI-agent team ({pkg}) handles {value} so you don't have to hire for it.\n"
                "Would it help if we prepared a short, personalized demo for your company?"
            )
        elif variant == VARIANT_CUSTOMER:
            message = (
                f"Hello {greeting_name}, this is the Al-Narjis AI team.\n"
                f"Glad to reconnect with {company or 'you'}.\n"
                f"We launched an AI-agent team ({pkg}) that takes over {value} — {pkg_value}.\n"
                "Shall we prepare a quick, personalized demo for your company?"
            )
        else:
            message = (
                f"Hello {greeting_name}, this is the Al-Narjis AI team.\n"
                f"We help businesses like {company or 'yours'} take over {value} using a dedicated AI-agent team ({pkg}).\n"
                "If useful, we'll prepare a short, personalized demo for your company. Shall I send it?"
            )
        signature = "— Al-Narjis AI team\nAl-Narjis AI · Riyadh"
    else:
        value = VALUE_BY_SEGMENT_AR.get(segment, VALUE_BY_SEGMENT_AR["unknown"])
        pkg = _package_name(package, lang)
        pkg_value = _package_value(package, lang)
        if variant == VARIANT_QUOTE:
            message = (
                f"السلام عليكم {greeting_name}، معك فريق النرجس للذكاء الاصطناعي.\n"
                f"لاحظنا أن {company or 'شركتكم'} طلبت عرض سعر سابقاً معنا، وتعمل في مجال "
                f"{value.split('،')[0]}.\n"
                f"جهّزنا فريق وكلاء AI ({pkg}) يتولى {pkg_value} بدل التوظيف.\n"
                "نقدر نرسل لكم Demo قصير ومخصص لشركتكم — يناسبكم؟"
            )
        elif variant == VARIANT_CUSTOMER:
            message = (
                f"السلام عليكم {greeting_name}، معك فريق النرجس للذكاء الاصطناعي.\n"
                f"سعيدين بعلاقتنا السابقة مع {company or 'شركتكم'}.\n"
                f"أطلقنا فريق وكلاء AI ({pkg}) يتولى {value}.\n"
                "نقترح نجهّز لكم Demo سريع ومخصص لشركتكم — مناسب؟"
            )
        else:
            message = (
                f"السلام عليكم {greeting_name}، معك فريق النرجس للذكاء الاصطناعي.\n"
                f"نساعد شركات مثل {company or 'شركتكم'} على الاستعانة بفريق وكلاء AI ({pkg}) "
                f"يتولى {value}.\n"
                "لو مناسب، نجهّز لكم Demo قصير ومخصص لشركتكم ونعرضه عليكم — أرسله لكم؟"
            )
        signature = "— فريق النرجس\nالنرجس للذكاء الاصطناعي · الرياض"

    message = f"{message}\n{signature}"

    phone = _val(lead, "phone")
    wa_number = wa_me_number(phone) if phone else None
    wa_link = f"https://wa.me/{wa_number}?text={quote(message)}" if wa_number else None

    return {
        "variant": variant,
        "variant_label": VARIANT_LABELS_AR.get(variant, variant),
        "message": message,
        "wa_link": wa_link,
        "wa_number": wa_number,
        "package": package,
        "package_name": _package_name(package, lang),
        "company_whatsapp": settings.whatsapp_business_number,
        "lang": lang,
    }
