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