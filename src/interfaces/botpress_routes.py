# Botpress routes
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix='/api/v1', tags=['botpress'])

class SocialWebhookRequest(BaseModel):
    clientName: Optional[str] = None
    clientEmail: Optional[str] = None
    clientPhone: Optional[str] = None
    chosenPackage: Optional[str] = None
    paymentStatus: Optional[str] = None
    leadId: Optional[str] = None
    payload: Optional[dict] = None

class KarmishTalkRequest(BaseModel):
    message: str
    sessionId: Optional[str] = None

@router.post('/social-webhook')
async def social_webhook(body: SocialWebhookRequest, request: Request):
    app = request.app
    cb = getattr(app.state, 'company_brain', None)
    if cb:
        try:
            await cb.process_event('botpress.social_closed_sale', {
                'client_name': body.clientName,
                'client_email': body.clientEmail,
                'client_phone': body.clientPhone,
                'package': body.chosenPackage,
                'payment_status': body.paymentStatus,
                'lead_id': body.leadId,
                'payload': body.payload,
            })
        except Exception:
            pass
    return {'success': True}

@router.post('/karmish/talk')
async def karmish_talk(body: KarmishTalkRequest):
    return {'reply': 'تم استلام الأمر: ' + body.message}

@router.post('/karmish-twin')
async def karmish_twin(body: SocialWebhookRequest, request: Request):
    return await social_webhook(body, request)

@router.post('/botpress-lead')
async def botpress_lead(body: SocialWebhookRequest, request: Request):
    if body.paymentStatus == 'success':
        app = request.app
        cb = getattr(app.state, 'company_brain', None)
        if cb:
            try:
                await cb.process_event('botpress.closed_sale', {
                    'manager': 'CEO_AlNarjis',
                    'package': body.chosenPackage,
                    'details': {'name': body.clientName, 'email': body.clientEmail, 'phone': body.clientPhone},
                    'lead_id': body.leadId,
                })
            except Exception:
                pass
        return {'success': True, 'message': 'تم إيقاظ الـ CEO وتوزيع المهام على الوكلاء بنجاح!'}
    raise HTTPException(status_code=400, detail='الصفقة غير مكتملة الدفع.')
