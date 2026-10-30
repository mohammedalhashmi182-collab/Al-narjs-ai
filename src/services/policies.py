"""Al-Narjis customer policies, decided by the owner (Mohammed) on 2026-10-13.

Single source of truth for every prompt, the owner FAQ seed, the checkout consent
and the terms/privacy wording. Change policy here, not in copies.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

POLICY_VERSION = "2026-10-24"

# Exact text the buyer must tick before any payment is created.
REFUND_CONSENT_AR = "الخدمة تبدأ بعد تفعيلها والمبلغ غير قابل للاسترداد بعد التفعيل، باستثناء رسوم الإعداد: إن لم يعمل الوكيل خلال 10 أيام عمل نسترد رسوم الإعداد فقط"
REFUND_CONSENT_EN = "The service starts once it is activated and the amount is non-refundable after activation, except the setup fee: if the agent is not working within 10 business days, we refund the setup fee only"

POLICY_PROMPT = (
    "Al-Narjis policies (owner-approved, never contradict them):\n"
    f"- Refunds: none after activation, except the setup fee as below. Before paying, the customer explicitly agrees to: «{REFUND_CONSENT_AR}». "
    "Always refunded: a duplicate charge or a technical billing error. Setup guarantee: only the one-time setup fee "
    "is refunded, in full, if the first agent is not live within 10 business days of receiving the requirements. Cancellation stops the next renewal; "
    "the current period is not refunded. Every refund request is escalated to the owner.\n"
    "- Support: by email at AlNarjisai@gmail.com. The Enterprise plan gets a reply within one business day. "
    "There is no phone support and no round-the-clock assistant.\n"
    "- Free trial: none. The only free thing is the diagnosis by the CEO advisor.\n"
    "- Meta WhatsApp fees: currently included in the subscription (Al-Narjis absorbs them). Say 'currently included'; "
    "never promise they will stay included permanently.\n"
    "- Data (Saudi PDPL): we collect the minimum; data is processed by AI providers outside Saudi Arabia; after "
    "cancellation conversations and files are kept 30 days, then deleted; invoices and payment records are retained "
    "as ZATCA requires; we delete on customer request except invoices; no selling and no marketing use without consent.\n"
    "- Web search, CSV/Excel uploads and the knowledge base are available; they are switched on for an account "
    "during setup, on request. Salla/Zid store connection is coming soon and is not included today; never say it is available."
)

OWNER_FAQ_TITLE = "سياسات النرجس الرسمية"

OWNER_FAQ_AR = f"""سياسة الاسترداد: لا يوجد استرداد بعد تفعيل الخدمة باستثناء رسوم الإعداد. قبل الدفع يوافق العميل صراحة على «{REFUND_CONSENT_AR}». الاستثناء اللي يُسترد دائماً: الخصم المكرر أو خطأ تقني في الفوترة. ضمان الإعداد: إذا لم يعمل أول وكيل خلال 10 أيام عمل من استلام المتطلبات تُرد رسوم الإعداد فقط كاملة. طلبات الاسترداد ترفع للمالك عبر البريد AlNarjisai@gmail.com.

الإلغاء: تقدر تلغي في أي وقت، والإلغاء يوقف التجديد القادم، وتبقى الخدمة شغالة حتى نهاية الفترة الحالية بدون استرداد لها، ويُغلق الفريق في نهاية الفترة المدفوعة.

أوقات الدعم: الدعم عبر البريد AlNarjisai@gmail.com. باقة الشركات يصلها الرد خلال يوم عمل. لا يوجد دعم هاتفي ولا مساعد على مدار الساعة.

التجربة المجانية: ما عندنا تجربة مجانية. المجاني هو التشخيص مع الرئيس التنفيذي الذكي فقط.

رسوم واتساب من Meta: رسوم رسائل واتساب الرسمية مشمولة حالياً في الاشتراك ونتحملها نحن، وأي تغيير نبلغك فيه مسبقاً قبل التجديد.

البيانات والخصوصية: نجمع أقل قدر لازم من البيانات، وتُعالج عبر مزودي ذكاء اصطناعي خارج المملكة. ما نبيع البيانات ولا نستخدمها للتسويق بدون موافقتك.

الاحتفاظ بالبيانات بعد الإلغاء: نحتفظ بالمحادثات والملفات 30 يوماً بعد الإلغاء ثم نحذفها. الفواتير وسجلات الدفع نحتفظ فيها حسب متطلبات هيئة الزكاة والضريبة والجمارك. وتقدر تطلب حذف بياناتك في أي وقت ما عدا الفواتير.

الأدوات: البحث في الويب، رفع ملفات CSV وExcel، وقاعدة المعرفة متاحة وتتفعّل لحسابك بالإعداد عند الطلب. ربط سلة أو زد «قريباً» وغير مشمول حالياً."""


async def seed_owner_faq(session: AsyncSession) -> bool:
    """Create or refresh the owner policy FAQ doc. Returns True when it changed."""
    from src.models.agent_tools import KnowledgeDoc

    row = (await session.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.project_id.is_(None), KnowledgeDoc.title == OWNER_FAQ_TITLE)
    )).scalars().first()
    if row is not None and row.content == OWNER_FAQ_AR:
        return False
    if row is None:
        session.add(KnowledgeDoc(project_id=None, title=OWNER_FAQ_TITLE, content=OWNER_FAQ_AR, source="policy"))
    else:
        row.content = OWNER_FAQ_AR
    await session.commit()
    return True
