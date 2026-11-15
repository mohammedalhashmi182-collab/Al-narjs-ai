"""Approved service-level figures for /sla.

The owner approved these terms. ``OWNER_REVIEW_REQUIRED`` stays false so the
public page does not show a draft banner. Prices are read from the catalog
at render time. The commitments below live here.
"""

from __future__ import annotations

# The owner approved the figures on this page.
OWNER_REVIEW_REQUIRED = False

# Monthly uptime commitment for every plan.
UPTIME_PERCENT = "99.0"

# First human reply, during the support window, by plan key.
RESPONSE_BY_PLAN: dict[str, dict[str, str]] = {
    "bidaya": {
        "ar": "رد أول خلال يوم عمل واحد",
        "en": "First reply within 1 business day",
    },
    "numuw": {
        "ar": "رد أول خلال يوم عمل واحد",
        "en": "First reply within 1 business day",
    },
    "sharikat": {
        "ar": "رد أول خلال 8 ساعات عمل",
        "en": "First reply within 8 business hours",
    },
}

SUPPORT_WINDOW_AR = "الأحد إلى الخميس، 9:00-17:00 بتوقيت الرياض"
SUPPORT_WINDOW_EN = "Sunday to Thursday, 09:00-17:00 Asia/Riyadh"

EXCLUSIONS_AR = (
    "يُستثنى من القياس: الصيانة المجدولة المعلنة قبل 24 ساعة على الأقل، "
    "وأعطال مزودي الطرف الثالث (استضافة Render، ومدفوعات Moyasar، ومزودو نماذج الذكاء الاصطناعي)، "
    "والمشكلات التي يسببها العميل، والظروف القاهرة."
)
EXCLUSIONS_EN = (
    "Excluded from the measurement: scheduled maintenance announced at least 24 hours "
    "in advance, outages of third-party providers (Render hosting, Moyasar payments, "
    "and AI model providers), customer-caused issues, and force majeure."
)

# A target, not a guarantee.
INCIDENT_AR = (
    "معالجة الحوادث الكبرى هدف وليست ضماناً: نبدأ العمل خلال 4 ساعات عمل، "
    "ونستهدف إعادة الخدمة خلال 24 ساعة."
)
INCIDENT_EN = (
    "Major-incident handling is a target, not a guarantee: we start working "
    "within 4 business hours and target resolution within 24 hours."
)

ESCALATION_AR = (
    "إذا تجاوز الانقطاع الكبير 4 ساعات، نُبلغ العملاء عبر بريدهم المسجّل، "
    "ونرسل تحديثاً كل ساعتين حتى تعود الخدمة."
)
ESCALATION_EN = (
    "If a major outage exceeds 4 hours, customers are notified by their registered "
    "email and receive an update every 2 hours until service is restored."
)

# Account credit on the next invoice, not cash. Percents of that month's
# subscription fee only (setup fees are outside the credit). The cap is 25%.
CREDITS: list[dict[str, str]] = [
    {
        "ar": "أقل من 99.0% وحتى 98.0%",
        "en": "Below 99.0% and at or above 98.0%",
        "credit_ar": "10% من رسوم الاشتراك لذلك الشهر",
        "credit_en": "10% of that month's subscription fee",
    },
    {
        "ar": "أقل من 98.0% وحتى 95.0%",
        "en": "Below 98.0% and at or above 95.0%",
        "credit_ar": "15% من رسوم الاشتراك لذلك الشهر",
        "credit_en": "15% of that month's subscription fee",
    },
    {
        "ar": "أقل من 95.0%",
        "en": "Below 95.0%",
        "credit_ar": "25% من رسوم الاشتراك لذلك الشهر",
        "credit_en": "25% of that month's subscription fee",
    },
]

CREDIT_CAP_AR = "السقف 25% من رسوم الاشتراك لذلك الشهر. رسوم الإعداد غير مشمولة."
CREDIT_CAP_EN = "The cap is 25% of that month's subscription fee. Setup fees are excluded."

REVIEW_CYCLE_AR = "تُراجع هذه الالتزامات كل ثلاثة أشهر وتُحدَّث حسب تطور البنية التحتية."
REVIEW_CYCLE_EN = (
    "These commitments are reviewed every three months and updated as our infrastructure evolves."
)
