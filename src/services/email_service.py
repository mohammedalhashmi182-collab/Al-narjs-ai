from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional

from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def is_configured() -> bool:
    return bool(settings.smtp_username and settings.smtp_password)


def _build_message(
    to: str,
    subject: str,
    body: str,
    html: Optional[str] = None,
) -> EmailMessage:
    msg = EmailMessage()
    from_name = "النرجس للذكاء الاصطناعي | Al-Narjis AI"
    from_addr = settings.smtp_from or settings.smtp_username
    msg["From"] = formataddr((from_name, from_addr))
    msg["To"] = to
    msg["Subject"] = subject
    if settings.mail_reply_to:
        msg["Reply-To"] = settings.mail_reply_to
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def _send_sync(msg: EmailMessage) -> None:
    host = settings.smtp_host or "smtp.gmail.com"
    port = settings.smtp_port or 587
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as server:
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)


async def send_email(
    to: str,
    subject: str,
    body: str,
    html: Optional[str] = None,
) -> bool:
    if not is_configured():
        logger.warning("SMTP not configured — email not sent to %s", to)
        return False

    try:
        msg = _build_message(to, subject, body, html)
        await asyncio.to_thread(_send_sync, msg)
        logger.info("Email sent to %s | subject=%s", to, subject)
        return True
    except Exception as e:
        logger.error("Email failed to %s: %s", to, e)
        return False


def _welcome_html(name: str) -> str:
    return f"""
    <div dir="rtl" style="font-family:Tahoma,Arial,sans-serif;max-width:560px;margin:auto;border:1px solid #e3dcc8;border-radius:14px;overflow:hidden;">
      <div style="background:#0b3d2e;color:#e6c665;text-align:center;padding:22px;">
        <div style="font-size:26px;">✺</div>
        <div style="font-size:20px;font-weight:bold;color:#fff;">النرجس للذكاء الاصطناعي</div>
        <div style="font-size:12px;letter-spacing:2px;color:#e6c665;">AL-NARJIS AI · RIYADH</div>
      </div>
      <div style="padding:26px;color:#3f3526;font-size:15px;line-height:1.9;">
        <p>أهلاً <b>{name}</b>،</p>
        <p>شكراً لاختيارك النرجس للذكاء الاصطناعي. استلمنا طلبك وسيتواصل معك فريقنا خلال ٢٤ ساعة.</p>
        <p style="color:#0b3d2e;font-weight:bold;">— فريق النرجس</p>
      </div>
    </div>
    """


async def send_welcome(to: str, name: str) -> bool:
    return await send_email(
        to=to,
        subject="أهلاً بك في النرجس للذكاء الاصطناعي ✺",
        body=f"""أهلاً {name}،

شكراً لاختيارك النرجس للذكاء الاصطناعي. استلمنا طلبك وسيتواصل معك فريقنا خلال ٢٤ ساعة.

— فريق النرجس
Al-Narjis AI · Riyadh""",
        html=_welcome_html(name),
    )


def _invoice_html(payment, base_halalas: int, vat_halalas: int, total_halalas: int, locale: str) -> str:
    package_name = {
        "social": "سوشيال ميديا / Social Media",
        "ecommerce": "متاجر إلكترونية / E-commerce",
        "content": "تسويق محتوى / Content Marketing",
        "growth": "نمو الأعمال / Business Growth",
    }.get(payment.package, payment.package or "")

    def fmt(halalas: int) -> str:
        return f"{halalas / 100:,.2f} SAR"

    ar = locale == "ar"
    label_org = "مؤسسة ذا أريبيان كونفو" if ar else "The Arabian Convoy Establishment"
    cr = "سجل تجاري 31332495263" if ar else "Commercial Reg. 31332495263"
    label_inv = "فاتورة / Invoice" if ar else "Invoice"
    label_pkg = "الباقة / Package" if ar else "Package"
    label_subtotal = "المبلغ قبل الضريبة / Subtotal" if ar else "Subtotal"
    label_vat = "ضريبة القيمة المضافة 15% / VAT 15%" if ar else "VAT 15%"
    label_total = "الإجمالي / Total" if ar else "Total"
    label_num = "فاتورة رقم" if ar else "Invoice No."

    vat_row = (
        f'<tr><td style="padding:8px 12px;color:#6b7280;">{label_vat}</td>'
        f'<td align="right" style="padding:8px 12px;">{fmt(vat_halalas)}</td></tr>'
    ) if vat_halalas else ""

    return f"""
    <div dir="{ 'rtl' if ar else 'ltr' }" style="font-family:Tahoma,Arial,sans-serif;max-width:600px;margin:auto;border:1px solid #d8d0bd;border-radius:14px;overflow:hidden;">
      <div style="background:#0a0b0e;color:#e6c98a;text-align:center;padding:22px;">
        <div style="font-size:20px;font-weight:bold;color:#fff;">النرجس للذكاء الاصطناعي</div>
        <div style="font-size:11px;letter-spacing:2px;color:#c8a45e;">AL-NARJIS AI · RIYADH</div>
      </div>
      <div style="padding:26px;color:#2b2620;font-size:14px;line-height:1.8;">
        <div style="display:flex;justify-content:space-between;font-weight:bold;border-bottom:2px solid #0a0b0e;padding-bottom:10px;">
          <span>{label_inv}</span>
          <span style="color:#6b7280;">{label_num} {str(payment.id)[:8].upper()}</span>
        </div>
        <p><b>{label_org}</b><br/>
           {cr}<br/>Riyadh, Kingdom of Saudi Arabia</p>
        <table style="width:100%;border-collapse:collapse;margin-top:12px;">
          <tr style="background:#f4f1e8;">
            <th align="left" style="padding:8px 12px;">{label_pkg}</th>
            <th align="right" style="padding:8px 12px;">{label_subtotal}</th>
          </tr>
          <tr>
            <td style="padding:8px 12px;">{package_name}</td>
            <td align="right" style="padding:8px 12px;">{fmt(base_halalas)}</td>
          </tr>
          {vat_row}
          <tr style="border-top:2px solid #0a0b0e;">
            <td style="padding:10px 12px;font-weight:bold;">{label_total}</td>
            <td align="right" style="padding:10px 12px;font-weight:bold;color:#0b3d2e;">{fmt(total_halalas)}</td>
          </tr>
        </table>
        <p style="color:#6b7280;font-size:12px;margin-top:16px;">
          {'شكراً لثقتك بالنرجس للذكاء الاصطناعي.' if ar else 'Thank you for choosing Al-Narjis AI.'}
          {' 🧾' if not ar else ''}
        </p>
      </div>
    </div>
    """


async def send_invoice(payment, base_halalas: int, total_halalas: int, locale: str = "ar", to: Optional[str] = None) -> bool:
    if not payment.customer_email and not to:
        return False
    vat = total_halalas - base_halalas
    subject = "فاتورتك من النرجس للذكاء الاصطناعي" if locale == "ar" else "Your invoice from Al-Narjis AI"
    return await send_email(
        to=to or payment.customer_email,
        subject=subject,
        body=f"Al-Narjis AI · Invoice {str(payment.id)[:8].upper()} · {total_halalas / 100:,.2f} SAR",
        html=_invoice_html(payment, base_halalas, vat, total_halalas, locale),
    )