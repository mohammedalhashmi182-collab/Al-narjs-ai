"""Owner-requested public contact; no guessed social accounts or founder portraits."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from src.config.settings import get_settings

_PATH = Path(__file__).resolve().parents[2] / "content" / "public_identity.json"
_SOCIAL_HOSTS = {
    "instagram.com",
    "www.instagram.com",
    "linkedin.com",
    "www.linkedin.com",
    "x.com",
    "www.youtube.com",
    "youtube.com",
    "www.tiktok.com",
    "tiktok.com",
    "facebook.com",
    "www.facebook.com",
}


def presence() -> dict:
    number = re.sub(r"[\s()+-]", "", get_settings().whatsapp_business_number or "")
    if re.fullmatch(r"05\d{8}", number):
        number = "966" + number[1:]
    whatsapp = ""
    if re.fullmatch(r"9665\d{8}", number):
        whatsapp = (
            "https://wa.me/"
            + number
            + "?"
            + urlencode({"text": "مرحباً، أود التعرف على خدمات النرجس للذكاء الاصطناعي."})
        )
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    links = []
    for item in data.get("social_links", []) if isinstance(data.get("social_links"), list) else []:
        if not isinstance(item, dict) or item.get("owner_verified") is not True:
            continue
        url = str(item.get("url") or "")
        try:
            parsed = urlsplit(url)
        except ValueError:
            continue
        if (
            parsed.scheme == "https"
            and parsed.netloc in _SOCIAL_HOSTS
            and parsed.path.strip("/")
            and item.get("label")
        ):
            links.append({"url": url, "label": str(item["label"])[:50]})
    portrait = data.get("founder_portrait")
    photo = None
    if isinstance(portrait, dict) and portrait.get("owner_approved") is True:
        name = str(portrait.get("filename") or "")
        if re.fullmatch(r"[a-zA-Z0-9_-]+\.(?:jpg|jpeg|png|webp)", name):
            file = _PATH.parents[0].parent / "src" / "web" / "static" / "founder" / name
            if file.is_file():
                photo = "/static/founder/" + name
    return {"whatsapp": whatsapp, "social_links": links, "founder_photo": photo}
