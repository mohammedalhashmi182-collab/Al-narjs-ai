"""Customer-service handoff target for the site assistant.

Configured only by environment so no number is ever hardcoded:
  SUPPORT_PHONE    E.164-ish number, e.g. +9665XXXXXXXX (digits and a leading +)
  SUPPORT_CHANNEL  "call" (tel: link) or "whatsapp" (wa.me link); default "call"
When SUPPORT_PHONE is unset or invalid the handoff falls back to email.
"""

from __future__ import annotations

import os
import re

SUPPORT_EMAIL = "Al-Narjis@karmaai.online"
_PHONE_RE = re.compile(r"^\+?\d{8,15}$")


def support_contact() -> dict:
    raw = re.sub(r"[\s\-()]", "", os.environ.get("SUPPORT_PHONE", "") or "")
    channel = (os.environ.get("SUPPORT_CHANNEL", "") or "call").strip().lower()
    if raw and _PHONE_RE.match(raw):
        digits = raw.lstrip("+")
        if channel == "whatsapp":
            return {"channel": "whatsapp", "href": f"https://wa.me/{digits}", "value": "+" + digits}
        return {"channel": "call", "href": f"tel:+{digits}", "value": "+" + digits}
    return {"channel": "email", "href": f"mailto:{SUPPORT_EMAIL}", "value": SUPPORT_EMAIL}
