"""Operations & compliance routes.

Public pages: /dpa, /subprocessors, /contact (PDPL + contact).
Owner API (cookie-authenticated, ``/api/owner/ops/*``):
  health                       GET  deep health (db + external), secret-free
  weekly-reports               GET ?status=draft ; POST generate
  weekly-reports/{id}/edit     POST {text}
  weekly-reports/{id}/approve  POST  (sends; template path outside 24h)
  weekly-reports/{id}/reject   POST
  wa-templates                 GET ; PUT {name} {status}
  wa/renewal/{outbound_id}     POST send a drafted renewal reminder via the template path
  qa/flagged                   GET  pending drafts with a low QA score
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select

from src.core.owner_auth import require_owner

router = APIRouter(tags=["ops"])
api = APIRouter(prefix="/api/owner/ops", dependencies=[Depends(require_owner)], tags=["ops"])

# Subprocessors: who processes customer data on our behalf. Keep in sync with
# docs/runbooks.md and the privacy policy. Only services the code actually calls.
SUBPROCESSORS = [
    {"name": "Render", "purpose_ar": "استضافة التطبيق وقاعدة البيانات", "purpose_en": "Application and database hosting",
     "region_ar": "الولايات المتحدة (منطقة Render الافتراضية: أوريغون)", "region_en": "USA (Render default region: Oregon)"},
    {"name": "Google (Gemini API)", "purpose_ar": "توليد ردود الذكاء الاصطناعي وتضمين النصوص", "purpose_en": "AI response generation and embeddings",
     "region_ar": "خارج المملكة", "region_en": "Outside KSA"},
    {"name": "Groq", "purpose_ar": "إجابة المساعد السريعة بعد إخفاء البيانات الشخصية", "purpose_en": "Fast assistant answers after PII masking",
     "region_ar": "خارج المملكة", "region_en": "Outside KSA"},
    {"name": "OpenAI", "purpose_ar": "المسار الأعمق للمساعد بعد إخفاء البيانات الشخصية", "purpose_en": "Deeper assistant answers after PII masking",
     "region_ar": "خارج المملكة", "region_en": "Outside KSA"},
    {"name": "Moonshot AI (Kimi)", "purpose_ar": "مزود ذكاء اصطناعي احتياطي", "purpose_en": "Fallback AI provider",
     "region_ar": "خارج المملكة", "region_en": "Outside KSA"},
    {"name": "Meta Platforms (WhatsApp Cloud API, Messenger)", "purpose_ar": "استقبال وإرسال رسائل واتساب وماسنجر",
     "purpose_en": "Receiving and sending WhatsApp and Messenger messages", "region_ar": "خارج المملكة", "region_en": "Outside KSA"},
    {"name": "Telegram", "purpose_ar": "قناة المحادثة وتنبيهات المالك", "purpose_en": "Chat channel and owner alerts",
     "region_ar": "خارج المملكة", "region_en": "Outside KSA"},
    {"name": "Brevo (SMTP / email API)", "purpose_ar": "إرسال البريد الإلكتروني (عند تفعيله)", "purpose_en": "Sending email (when enabled)",
     "region_ar": "خارج المملكة", "region_en": "Outside KSA"},
    {"name": "Moyasar", "purpose_ar": "معالجة المدفوعات بالبطاقة", "purpose_en": "Card payment processing",
     "region_ar": "شركة سعودية", "region_en": "Saudi company"},
    {"name": "PayPal", "purpose_ar": "مسار دفع غير متاح للعملاء (الدفع عبر ميسر فقط)", "purpose_en": "Payment path not offered to customers (Moyasar only)",
     "region_ar": "خارج المملكة", "region_en": "Outside KSA"},
]

RETENTION = [
    {"data_ar": "المحادثات والملفات المرفوعة وقاعدة المعرفة", "data_en": "Conversations, uploaded files and knowledge base",
     "period_ar": "مدة الاشتراك + 30 يوماً بعد الإلغاء ثم تُحذف", "period_en": "Subscription term + 30 days after cancellation, then deleted"},
    {"data_ar": "الفواتير وسجلات الدفع", "data_en": "Invoices and payment records",
     "period_ar": "حسب متطلبات هيئة الزكاة والضريبة والجمارك (ZATCA)", "period_en": "As required by ZATCA"},
    {"data_ar": "سجلات التشغيل الفنية", "data_en": "Technical operation logs",
     "period_ar": "حتى 90 يوماً", "period_en": "Up to 90 days"},
    {"data_ar": "بيانات العملاء المحتملين الذين طلبوا عدم التواصل", "data_en": "Leads who opted out",
     "period_ar": "نحتفظ بالرقم فقط في قائمة عدم التواصل لضمان احترام طلبهم", "period_en": "Only the number is kept on the do-not-contact list so the request is honoured"},
]


def _render(request: Request, name: str, ctx: dict | None = None):
    from src.main import templates
    from src.services import transfer

    from src.main import _page_lang

    base = {
        "contact": transfer.contact_channels(),
        "subprocessors": SUBPROCESSORS,
        "retention": RETENTION,
        "ar": _page_lang(request) == "ar",
    }
    return templates.TemplateResponse(request, name, {**base, **(ctx or {})})


@router.get("/dpa", response_class=HTMLResponse)
async def dpa_page(request: Request):
    return _render(request, "dpa.html")


@router.get("/subprocessors", response_class=HTMLResponse)
async def subprocessors_page(request: Request):
    return _render(request, "subprocessors.html")


@router.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    return _render(request, "contact.html")


# --------------------------------------------------------------------------- owner API

class TextBody(BaseModel):
    text: str


class StatusBody(BaseModel):
    status: str


def _factory(request: Request):
    return request.app.state.session_factory


def _uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(422, "invalid id")


@api.get("/health")
async def owner_health(request: Request):
    from src.services import ops_monitor

    return await ops_monitor.deep_health(_factory(request))


@api.get("/weekly-reports")
async def list_reports(request: Request, status: str | None = "draft"):
    from src.models.ops import WeeklyReport
    from src.services import weekly_reports

    async with _factory(request)() as s:
        q = select(WeeklyReport).order_by(WeeklyReport.week_start.desc()).limit(200)
        if status:
            q = q.where(WeeklyReport.status == status)
        return {"reports": [weekly_reports.to_dict(r) for r in (await s.execute(q)).scalars()]}


@api.post("/weekly-reports/generate")
async def generate_reports(request: Request):
    from src.services import weekly_reports

    async with _factory(request)() as s:
        reps = await weekly_reports.generate_all(s)
        return {"drafted": len(reps), "reports": [weekly_reports.to_dict(r) for r in reps]}


async def _report_action(request: Request, report_id: str, action, *args):
    from src.services import weekly_reports

    async with _factory(request)() as s:
        try:
            rep = await action(s, _uuid(report_id), *args)
        except LookupError:
            raise HTTPException(404, "report not found")
        except ValueError as e:
            raise HTTPException(409, str(e))
        await s.commit()
        return weekly_reports.to_dict(rep)


@api.post("/weekly-reports/{report_id}/edit")
async def edit_report(report_id: str, body: TextBody, request: Request):
    from src.services import weekly_reports

    return await _report_action(request, report_id, weekly_reports.edit, body.text)


@api.post("/weekly-reports/{report_id}/approve")
async def approve_report(report_id: str, request: Request):
    from src.services import weekly_reports

    return await _report_action(request, report_id, weekly_reports.approve_and_send)


@api.post("/weekly-reports/{report_id}/reject")
async def reject_report(report_id: str, request: Request):
    from src.services import weekly_reports

    return await _report_action(request, report_id, weekly_reports.reject)


@api.get("/wa-templates")
async def list_templates(request: Request):
    from src.models.ops import WhatsAppTemplate
    from src.services import wa_templates

    async with _factory(request)() as s:
        await wa_templates.seed_defaults(s)
        await s.commit()
        rows = (await s.execute(select(WhatsAppTemplate).order_by(WhatsAppTemplate.name))).scalars()
        return {"templates": [{"name": r.name, "language": r.language, "category": r.category, "purpose": r.purpose,
                               "body": r.body, "param_count": r.param_count, "status": r.status} for r in rows]}


@api.put("/wa-templates/{name}")
async def set_template_status(name: str, body: StatusBody, request: Request):
    from src.services import wa_templates

    async with _factory(request)() as s:
        try:
            row = await wa_templates.set_status(s, name, body.status)
        except ValueError:
            raise HTTPException(400, "unknown status")
        except LookupError:
            raise HTTPException(404, "template not found")
        await s.commit()
        return {"name": row.name, "status": row.status}


@api.post("/wa/renewal/{outbound_id}")
async def send_renewal_reminder(outbound_id: str, request: Request):
    """Send one drafted renewal reminder (created by the renewal pass) via the 24h/template path."""
    from src.config.settings import get_settings
    from src.models import ClientProject, OutboundMessage
    from src.services import catalog, wa_templates

    async with _factory(request)() as s:
        msg = await s.get(OutboundMessage, _uuid(outbound_id))
        if msg is None or msg.message_type != "renewal":
            raise HTTPException(404, "renewal reminder not found")
        if msg.status != "draft":
            raise HTTPException(409, "reminder already handled")
        digits = "".join(c for c in (msg.phone or "") if c.isdigit())
        project = None
        if digits:
            project = (await s.execute(
                select(ClientProject).where(ClientProject.phone.like(f"%{digits[-9:]}"))
                .order_by(ClientProject.created_at.desc()).limit(1))).scalar_one_or_none()
        params = []
        if project is not None:
            base = (get_settings().public_base_url or str(request.base_url)).rstrip("/")
            pkg = catalog.PACKAGES.get(catalog.resolve_tier(project.package), {})
            end = project.current_period_end.date().isoformat() if project.current_period_end else "-"
            link = f"{base}/invoice/{project.renewal_payment_id}" if project.renewal_payment_id else base
            params = [project.client_name, pkg.get("name", project.package), end, link]
        res = await wa_templates.send_business_initiated(s, phone=msg.phone, purpose="renewal", text=msg.text,
                                                         params=params, lead_id=msg.lead_id)
        msg.status = "dispatched"
        await s.commit()
        return res


@api.get("/qa/flagged")
async def qa_flagged(request: Request):
    from src.services import smart_reply

    async with _factory(request)() as s:
        drafts = await smart_reply.list_drafts(s, status="pending", limit=200)
        flagged = [smart_reply.draft_to_dict(d) for d in drafts if ((d.meta or {}).get("qa") or {}).get("flagged")]
        flagged.sort(key=lambda d: d["qa_score"] if d["qa_score"] is not None else 100)
        return {"drafts": flagged}
