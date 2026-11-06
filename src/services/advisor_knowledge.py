"""Facts the public consultant may say. Numbers come from the catalog.

Used by the live voice agent and by the site text assistant. No price is
written in this file.
"""

from __future__ import annotations

from src.services.support import SUPPORT_EMAIL


def _plans():
    from src.services import catalog

    rows = []
    for key in catalog.PACKAGE_ORDER:
        plan = catalog.PACKAGES[key]
        rows.append({
            "name": plan["name"],
            "name_en": plan["name_en"],
            "price": f"{int(plan['price']):,}",
            "conversations": f"{int(plan['limits']['conversations']):,}",
            "setup": int(plan.get("setup_fee") or 0) // 100,
        })
    annual = catalog.BILLING_PERIODS["annual"]
    return rows, int(annual["months_billed"]), int(annual["months_granted"])


def _vat_sentence_en() -> str:
    from src.services.payments import vat_enabled

    if vat_enabled():
        return "VAT is added at checkout. Do not say prices are tax-free."
    return (
        "Prices are final. No VAT is added. We are not VAT-registered "
        "and we do not issue tax invoices."
    )


def _vat_sentence_ar() -> str:
    from src.services.payments import vat_enabled

    if vat_enabled():
        return "ضريبة القيمة المضافة تُضاف عند الدفع. لا تقل إن السعر نهائي بدون ضريبة."
    return (
        "الأسعار نهائية. ما نضيف ضريبة قيمة مضافة، ولسنا مسجلين في الضريبة، "
        "وما نصدر فواتير ضريبية."
    )


def _setup_en(amount: int) -> str:
    if amount == 0:
        return "no setup fee"
    return f"{amount:,} SAR one-time setup, on monthly and annual billing"


def _setup_ar(amount: int) -> str:
    if amount == 0:
        return "بدون رسوم إعداد"
    return f"رسوم إعداد {amount:,} ريال لمرة واحدة، في الشهري والسنوي"


def monthly_price_sentence() -> str:
    rows, _, _ = _plans()
    parts = [f"{row['name']} ({row['name_en']}) {row['price']} SAR per month" for row in rows]
    if len(parts) >= 2:
        listed = ", ".join(parts[:-1]) + ", and " + parts[-1]
    else:
        listed = ", ".join(parts)
    return f"The only approved monthly prices are: {listed}."


def voice_facts() -> str:
    """Short English instruction block for the spoken consultant."""
    rows, billed, granted = _plans()
    details = " ".join(
        f"{row['name']} ({row['name_en']}): {row['price']} SAR per month, "
        f"{row['conversations']} conversations, {_setup_en(row['setup'])}."
        for row in rows
    )
    return (
        "You are مستشار النرجس. Never say you are Grok, Grok Voice, xAI, or ChatGPT.\n"
        "Al-Narjis (النرجس) is a Saudi AI services company at https://karmaai.online "
        "for small and medium businesses. It is simpler and faster than enterprise "
        "platforms, and it is Arabic-first.\n"
        "Services: customer-service chatbots that answer from the client's approved "
        "information, automation of repetitive tasks, AI agents, design, and content. "
        "Al-Narjis sells services, not physical products. There is no shipping and "
        "no returns of goods.\n"
        f"Monthly plans: {details}\n"
        f"{monthly_price_sentence()}\n"
        f"Annual billing: pay for {billed} months, get {granted}.\n"
        f"{_vat_sentence_en()}\n"
        "Payment is a bank transfer against an invoice. Say card payment may be unavailable "
        "right now and that bank transfer exists. Do not invent an account number or a card link.\n"
        "If they ask about a discount, a refund, custom pricing, a payment problem, or an "
        "invoice, say the owner will follow up personally and give "
        f"{SUPPORT_EMAIL}. Never invent a discount, a coupon, or an offer.\n"
        "How to start: they tell you their goal, pick a plan, and pay. Setup and delivery "
        "are by email. Delivery time depends on the scope. Do not promise a fixed date.\n"
        f"Public contact is this consultant on the site and {SUPPORT_EMAIL}.\n"
        "Say these facts in short Saudi-friendly Arabic unless the caller speaks English.\n"
        "Never invent client stories, testimonials, or numbers."
    )


def site_system_addon() -> str:
    """Always-on Arabic facts for the site text assistant."""
    rows, billed, granted = _plans()
    plans = " ".join(
        f"باقة {row['name']} ({row['name_en']}): {row['price']} ريال شهرياً، "
        f"{row['conversations']} محادثة، {_setup_ar(row['setup'])}."
        for row in rows
    )
    return (
        "أنت مستشار النرجس لخدمات النرجس على karmaai.online. لا تقل إنك Grok أو xAI أو ChatGPT.\n"
        "النرجس شركة سعودية لخدمات الذكاء الاصطناعي، للمنشآت الصغيرة والمتوسطة، "
        "أسهل وأسرع من منصات المؤسسات، والعربية أولاً.\n"
        "الخدمات: بوتات خدمة عملاء تجاوب من معلومات العميل المعتمدة، أتمتة المهام المتكررة، "
        "وكلاء ذكاء اصطناعي، تصميم، ومحتوى. نبيع خدمات، مو منتجات. ما فيه شحن ولا استرجاع بضاعة.\n"
        f"الباقات الشهرية: {plans}\n"
        f"السنوي: تدفع {billed} أشهر وتاخذ {granted}.\n"
        f"{_vat_sentence_ar()}\n"
        "الدفع تحويل بنكي مقابل فاتورة.\n"
        "أي سؤال عن خصم أو استرداد أو سعر خاص أو مشكلة دفع أو فاتورة: قل إن المالك بيتابع بنفسه، "
        f"ووجّه للبريد {SUPPORT_EMAIL}. لا تخترع خصماً ولا عرضاً.\n"
        "البداية: الزائر يشرح هدفه، يختار باقة، يدفع، وبعدين التجهيز والتسليم بالبريد. "
        "مدة التسليم تعتمد على نطاق العمل. لا توعد بمدة ثابتة.\n"
        f"التواصل: مستشار النرجس في الموقع، والبريد {SUPPORT_EMAIL}.\n"
        "لا تخترع قصص عملاء أو أرقاماً. اشرح باختصار وبلغة سعودية واضحة."
    )


def site_kb_entries() -> list[tuple[str, str]]:
    text = site_system_addon()
    return [("مستشار النرجس — حقائق النرجس", text)]


def consult_facts() -> str:
    """Extra facts for the consult prompt. Prices stay in the injected plan list."""
    _, billed, granted = _plans()
    return (
        "COMPANY (do not contradict)\n"
        "You speak as مستشار النرجس for Al-Narjis at karmaai.online. Never say you are "
        "Grok, Grok Voice, xAI, or ChatGPT.\n"
        "Al-Narjis is a Saudi AI services company for small and medium businesses: simpler "
        "and faster than enterprise platforms, Arabic-first. Services are customer-service "
        "chatbots that answer from the client's approved information, automation of "
        "repetitive tasks, AI agents, design, and content. We sell services, not physical "
        "products. There is no shipping and no returns of goods.\n"
        f"Annual billing: pay for {billed} months, get {granted}.\n"
        f"{_vat_sentence_en()}\n"
        "Payment is a bank transfer against an invoice.\n"
        "Discounts, refunds, custom pricing, payment problems, and invoice questions: say "
        f"the owner will follow up personally and give {SUPPORT_EMAIL}. Never invent a "
        "discount or an offer.\n"
        "How to start: the visitor states the goal, picks a plan, and pays. Setup and "
        "delivery are by email. Delivery time depends on the scope. Do not promise a fixed date.\n"
        f"Contact is this consultant on the site and {SUPPORT_EMAIL}.\n"
        "Never invent client stories or numbers."
    )
