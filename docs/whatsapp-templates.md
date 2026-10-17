# WhatsApp message templates (submit to Meta)

Meta delivers free-form WhatsApp text only within **24 hours** of the customer's
last inbound message. Anything business-initiated after that (renewal
reminders, follow-ups, payment links, weekly reports) needs a **pre-approved
template**. The code registry lives in `src/services/wa_templates.py`
(`DEFAULT_TEMPLATES`) and the table `wa_message_templates`.

## How sending works

`wa_templates.send_business_initiated(...)`:

1. Customer wrote within 24h → plain text via `whatsapp_sender.send_now`.
2. Outside 24h and a template for that purpose has status `approved` → template message.
3. Otherwise (template not approved, WhatsApp not configured, or the send failed) →
   **fallback**: an `outbound_messages` row with status `awaiting_manual`,
   queued for the owner, plus an owner alert. Nothing is marked sent without a Meta ack.

Wired today: smart-reply follow-ups and payment links (`ReplyDraft.kind`
`followup` / `payment_link` on WhatsApp), weekly reports on approval, and
drafted renewal reminders via `POST /api/owner/ops/wa/renewal/{outbound_id}`.
The daily renewal pass itself (`renewals.py`) is unchanged.

## Templates to submit (Meta Business Manager → WhatsApp Manager → Message templates)

| Name | Category | Language | Purpose | Body (parameters {{n}}) |
|---|---|---|---|---|
| `renewal_reminder_ar` | Utility | Arabic (ar) | renewal | مرحباً {{1}}، اشتراكك في باقة {{2}} لدى النرجس للذكاء الاصطناعي ينتهي في {{3}}. رابط فاتورة التجديد: {{4}} |
| `followup_ar` | Marketing | Arabic (ar) | followup | مرحباً {{1}}، نتابع معك بخصوص طلبك لدى النرجس للذكاء الاصطناعي. هل تحب نكمل؟ رد على هذه الرسالة وبنساعدك. |
| `payment_link_ar` | Utility | Arabic (ar) | payment_link | مرحباً {{1}}، هذا رابط الدفع الآمن لباقة {{2}}: {{3}} |
| `weekly_report_ar` | Utility | Arabic (ar) | weekly_report | مرحباً {{1}}، تقريرك الأسبوعي من النرجس للذكاء الاصطناعي جاهز: {{2}} محادثة هذا الأسبوع. رد على هذه الرسالة لنرسل لك التفاصيل. |

Sample values for Meta review: `{{1}}`=سارة, `{{2}}`=بيع, `{{3}}`=2026-11-01, `{{4}}`=https://karmaai.online/invoice/…

## After Meta approves a template

The name and language in Meta must match the table exactly. Then mark it approved:

```
PUT /api/owner/ops/wa-templates/<name>   {"status": "approved"}
```

(`GET /api/owner/ops/wa-templates` lists all with their status.) If Meta rejects
or pauses one, set `rejected` / `paused`; sends fall back to the manual path.
