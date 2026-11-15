"""Partnerships page content.

Live rows are integrations the product actually runs. Planned rows are marked
in development. This module never supplies a launch date.
"""

from __future__ import annotations

from typing import Any

# Owner-set white-label prices, SAR, no VAT added here.
HOSTED_SETUP_SAR = 4900
HOSTED_MONTHLY_SAR = 1490
STANDALONE_SETUP_SAR = 9900
STANDALONE_SUPPORT_SAR = 1000


def live_integrations() -> list[dict[str, Any]]:
    """Integrations that exist in the product today."""
    from src.services import payments

    moyasar_live = payments.moyasar_collects_money()
    paypal_live = payments.paypal_checkout_open()
    return [
        {
            "key": "moyasar",
            "name": "Moyasar",
            "status": "available" if moyasar_live else "built",
            "ar": "دفع البطاقة للزائر (مدى وفيزا وماستركارد) يمر عبر Moyasar. لا نعرض مفتاحاً سرياً في هذه الصفحة.",
            "en": "Guest card checkout (mada, Visa, and Mastercard) runs through Moyasar. This page does not show a secret key.",
            "badge_ar": "متاح" if moyasar_live else "مُدمج في الدفع",
            "badge_en": "Available" if moyasar_live else "Built into checkout",
        },
        {
            "key": "voice",
            "name": "Voice advisor",
            "status": "available",
            "ar": "المستشار الصوتي العام موجود على صفحة /voice. مفتاح المزود يبقى على الخادم.",
            "en": "The public voice advisor is on /voice. The provider key stays on the server.",
            "badge_ar": "متاح",
            "badge_en": "Available",
        },
        {
            "key": "paypal",
            "name": "PayPal",
            "status": "available" if paypal_live else "optional",
            "ar": "PayPal مسار اختياري في الكود. يظهر في الدفع فقط عندما يفعّله المالك بوضع حي.",
            "en": "PayPal is an optional path in the code. Checkout shows it only when the owner enables live mode.",
            "badge_ar": "متاح" if paypal_live else "يُعرض عند التفعيل",
            "badge_en": "Available" if paypal_live else "Shown when enabled",
        },
    ]


def planned_integrations() -> list[dict[str, str]]:
    """Not offered. No dates. Do not describe these as available."""
    return [
        {
            "key": "salla",
            "name": "Salla",
            "status": "in_development",
            "ar": "ربط سلة قيد التطوير. لا يمكن ربط متجر سلة من البوابة اليوم.",
            "en": "A Salla connection is in development. A Salla store cannot be connected from the portal today.",
            "badge_ar": "قيد التطوير",
            "badge_en": "In development",
        },
        {
            "key": "zid",
            "name": "Zid",
            "status": "in_development",
            "ar": "ربط زد قيد التطوير. لا يمكن ربط متجر زد من البوابة اليوم.",
            "en": "A Zid connection is in development. A Zid store cannot be connected from the portal today.",
            "badge_ar": "قيد التطوير",
            "badge_en": "In development",
        },
        {
            "key": "whatsapp",
            "name": "WhatsApp",
            "status": "in_development",
            "ar": "ربط واتساب للأعمال بمحادثات عملائك قيد التطوير. رابط التواصل العام في الموقع ليس هذا الربط.",
            "en": "WhatsApp Business for your own customer conversations is in development. The public contact link on the site is not this connection.",
            "badge_ar": "قيد التطوير",
            "badge_en": "In development",
        },
    ]


def white_label() -> dict[str, Any]:
    return {
        "hosted_setup": HOSTED_SETUP_SAR,
        "hosted_monthly": HOSTED_MONTHLY_SAR,
        "standalone_setup": STANDALONE_SETUP_SAR,
        "standalone_support": STANDALONE_SUPPORT_SAR,
    }
