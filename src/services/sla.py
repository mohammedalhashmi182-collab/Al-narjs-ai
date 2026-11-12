"""Service-level figures for /sla.

OWNER REVIEW REQUIRED. These numbers are a startup proposal so the page can
exist. They are not a signed commitment until the owner sets
``OWNER_REVIEW_REQUIRED`` to False after approving every figure below.

Prices are read from the catalog at render time. The response targets and
the credit table live here.
"""

from __future__ import annotations

# Flip to False only after the owner has approved every number on this page.
OWNER_REVIEW_REQUIRED = True

# Monthly uptime target for every plan. Measured on the public status feed.
UPTIME_PERCENT = "99.5"

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

# Account credit on the next invoice, not cash. Percents of that month's
# subscription fee only (setup fees are outside the credit).
CREDITS: list[dict[str, str]] = [
    {
        "ar": "من 99.0% وحتى أقل من 99.5%",
        "en": "From 99.0% up to, but not including, 99.5%",
        "credit_ar": "10% من رسوم الاشتراك لذلك الشهر",
        "credit_en": "10% of that month's subscription fee",
    },
    {
        "ar": "من 95.0% وحتى أقل من 99.0%",
        "en": "From 95.0% up to, but not including, 99.0%",
        "credit_ar": "25% من رسوم الاشتراك لذلك الشهر",
        "credit_en": "25% of that month's subscription fee",
    },
    {
        "ar": "أقل من 95.0%",
        "en": "Below 95.0%",
        "credit_ar": "50% من رسوم الاشتراك لذلك الشهر",
        "credit_en": "50% of that month's subscription fee",
    },
]

CREDIT_CAP_AR = "السقف 50% من رسوم الاشتراك لذلك الشهر. رسوم الإعداد غير مشمولة."
CREDIT_CAP_EN = "The cap is 50% of that month's subscription fee. Setup fees are excluded."
