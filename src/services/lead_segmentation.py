"""Transparent, keyword-based business segmentation.

Only uses information actually present in the imported data (company name and
known identifiers). If nothing matches confidently the segment is ``unknown`` —
we never invent company attributes.
"""

from __future__ import annotations

from typing import Optional

from src.services.lead_normalize import company_name_key

# segment -> keywords (Arabic + English). Longer keywords score more (more specific).
SEGMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ecommerce": (
        "متجر", "متاجر", "الكترون", "الإلكترون", "الالكترون", "اون لاين", "أون لاين",
        "online", "e-commerce", "ecommerce", "store", "shop", "شوب",
    ),
    "retail": (
        "تجزئه", "تجزئة", "بقال", "بقالة", "سوبر ماركت", "سوبرماركت", "هايبر",
        "تموين", "اسواق", "أسواق", "سوق", "معرض", "محل", "بيع", "market", "retail",
        "grocery", "hyper",
    ),
    "restaurant_food": (
        "مطعم", "مطاعم", "مقهى", "مقاهي", "كافيه", "كوفي", "قهوة", "حلويات", "حلى",
        "مخبز", "مخابز", "خبز", "مخبوزات", "اغذية", "أغذية", "غذائي", "غذائية", "اغذيه",
        "طعام", "وجبات", "بحار", "اسماك", "أسماك", "لحوم", "دواجن", "فطائر", "مثلجات",
        "ايس كريم", "آيس كريم", "عصائر", "شوكولات", "تمور", "اعاشة", "إعاشة", "بوفيه",
        "restaurant", "cafe", "coffee", "food", "bakery", "sweets", "catering",
    ),
    "services": (
        "خدمات", "صيانة", "نظافة", "تنظيف", "حراسة", "امن", "أمن", "نقل", "شحن",
        "لوجست", "سفر", "سياحة", "حج", "عمرة", "توصيل", "تقنية", "تقنيه", "حاسوب",
        "برمجة", "شبكات", "اتصالات", "دعاية", "اعلان", "إعلان", "تسويق", "تصميم",
        "طباعة", "تركيب", "كهرباء", "سباكة", "تكييف", "طاقة", "شمسية", "سيبراني",
        "استقدام", "تشغيل", "technology", "software", "logistics", "maintenance",
        "cleaning", "marketing", "advertising", "travel", "tours", "delivery",
    ),
    "professional_services": (
        "محام", "محاماه", "محامين", "قانون", "قانونية", "استشار", "محاسب", "محاسبة",
        "تدقيق", "مراجع", "مالي", "مالية", "ضريبي", "زكاة", "تأمين", "وساطة", "موارد بشرية",
        "consulting", "accounting", "audit", "legal", "law", "insurance",
    ),
    "education": (
        "مدرسة", "مدارس", "تعليم", "تعليمية", "تدريب", "اكاديمية", "أكاديمية", "اكاديميه",
        "معاهد", "معهد", "جامعة", "حضانة", "روضة", "دورات", "كورس", "تدريس", "تحفيظ",
        "education", "training", "academy", "school", "institute", "university", "nursery",
    ),
    "beauty": (
        "تجميل", "صالون", "كوافير", "حلاق", "عطور", "مكياج", "عناية", "بشرة", "شعر",
        "سبا", "مساج", "beauty", "salon", "spa", "perfume", "cosmetic", "barber",
    ),
    "real_estate": (
        "عقار", "عقاري", "عقارات", "اراضي", "أراضي", "تطوير عقاري", "تمليك", "ايجار",
        "إيجار", "real estate", "property", "realty", "realestate",
    ),
    "healthcare": (
        "مستشفى", "مستشفي", "عيادة", "عيادات", "طبي", "طبية", "صيدلية", "صيدليات",
        "اسنان", "أسنان", "مختبر", "تحاليل", "تمريض", "صحة", "صحي", "health", "medical",
        "clinic", "hospital", "pharmacy", "dental",
    ),
    # Only explicit industry-generic words; legal words like "شركة" are intentionally absent.
    "other": (
        "مقاولات", "مقاول", "صناعة", "مصنع", "مصانع", "ورشة", "حدادة", "نجارة",
        "الومنيوم", "زجاج", "رخام", "مواد بناء", "تجهيزات", "توريدات", "صناعي",
        "contracting", "manufacturing", "factory",
    ),
}

# Higher number = higher confidence/relevance for Karma AI packages.
SEGMENT_RELEVANCE: dict[str, int] = {
    "ecommerce": 10,
    "retail": 10,
    "restaurant_food": 10,
    "beauty": 10,
    "services": 8,
    "professional_services": 8,
    "education": 8,
    "real_estate": 8,
    "healthcare": 6,
    "other": 3,
    "unknown": 0,
}

SEGMENT_LABELS_AR: dict[str, str] = {
    "ecommerce": "تجارة إلكترونية",
    "retail": "تجزئة",
    "restaurant_food": "مطاعم وأغذية",
    "services": "خدمات",
    "professional_services": "خدمات مهنية",
    "education": "تعليم وتدريب",
    "beauty": "تجميل وعناية",
    "real_estate": "عقارات",
    "healthcare": "صحة",
    "other": "أخرى",
    "unknown": "غير محدد",
}

SEGMENT_LABELS_EN: dict[str, str] = {
    "ecommerce": "E-commerce",
    "retail": "Retail",
    "restaurant_food": "Restaurants & Food",
    "services": "Services",
    "professional_services": "Professional Services",
    "education": "Education",
    "beauty": "Beauty & Care",
    "real_estate": "Real Estate",
    "healthcare": "Healthcare",
    "other": "Other",
    "unknown": "Unknown",
}

# Preferred Karma AI package per segment.
SEGMENT_PACKAGE: dict[str, str] = {
    "ecommerce": "ecommerce",
    "retail": "ecommerce",
    "restaurant_food": "social",
    "beauty": "social",
    "services": "social",
    "real_estate": "social",
    "healthcare": "content",
    "education": "content",
    "professional_services": "content",
    "other": "growth",
    "unknown": "social",
}


def classify(text: Optional[str]) -> tuple[str, str]:
    """Return ``(segment, reason)`` for a company name / activity text."""
    key = company_name_key(text)
    if not key:
        return "unknown", "لا توجد بيانات كافية للتصنيف"

    scores: dict[str, int] = {}
    matches: dict[str, list[str]] = {}
    for segment, keywords in SEGMENT_KEYWORDS.items():
        score = 0
        found: list[str] = []
        for kw in keywords:
            if kw in key:
                score += len(kw)
                found.append(kw)
        if score:
            scores[segment] = score
            matches[segment] = found

    if not scores:
        return "unknown", "لا كلمات مفتاحية مطابقة"

    # Deterministic tie-break: higher score, then fixed order of SEGMENT_KEYWORDS.
    order = list(SEGMENT_KEYWORDS)
    best = max(scores, key=lambda s: (scores[s], -order.index(s)))
    top = ", ".join(matches[best][:3])
    return best, f"تصنيف آلي حسب كلمات النشاط: {top}"


def suggest_package(segment: str) -> str:
    return SEGMENT_PACKAGE.get(segment, "social")


def label(segment: str, lang: str = "ar") -> str:
    table = SEGMENT_LABELS_EN if lang == "en" else SEGMENT_LABELS_AR
    return table.get(segment, segment)
