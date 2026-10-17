"""Fernet for store tokens, separate from the WhatsApp token key.

Ciphertext is ``v1.<key id>.<fernet token>``.

* ``STORE_TOKEN_ENC_KEY`` — urlsafe-base64 Fernet key. Production must set it.
* ``STORE_TOKEN_ENC_KEY_ID`` — id written into new ciphertext (default ``1``).
* ``STORE_TOKEN_ENC_PREVIOUS_KEYS`` — comma-separated ``id:key`` pairs, decrypt only.

When ``STORE_TOKEN_ENC_KEY`` is unset, the key is derived from ``SECRET_KEY``
with the salt ``store-token-v1`` (not the WhatsApp salt). That fallback is for
local tests: rotating ``SECRET_KEY`` then makes stored store tokens unreadable.
Once the dedicated key is set, rotating ``SECRET_KEY`` does not rotate them.
To rotate the store key, put the old ``id:key`` in ``STORE_TOKEN_ENC_PREVIOUS_KEYS``
and point ``STORE_TOKEN_ENC_KEY`` / ``STORE_TOKEN_ENC_KEY_ID`` at the new key.
Refresh re-seals with the current key.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
from typing import Optional

from src.integrations.config import env

log = logging.getLogger(__name__)

_ID = re.compile(r"[A-Za-z0-9_-]{1,16}")


def _valid_id(value: str) -> bool:
    return bool(_ID.fullmatch(value or ""))


def _derived():
    from cryptography.fernet import Fernet

    from src.config.settings import settings

    raw = hashlib.sha256(f"store-token-v1:{settings.secret_key}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(raw))


def _keys() -> tuple[str, dict]:
    from cryptography.fernet import Fernet

    current_id = env("STORE_TOKEN_ENC_KEY_ID") or "1"
    if not _valid_id(current_id):
        current_id = "1"
    material = env("STORE_TOKEN_ENC_KEY")
    keys: dict = {}
    keys[current_id] = Fernet(material.encode()) if material else _derived()
    for piece in env("STORE_TOKEN_ENC_PREVIOUS_KEYS").split(","):
        piece = piece.strip()
        if ":" not in piece:
            continue
        kid, key = piece.split(":", 1)
        kid, key = kid.strip(), key.strip()
        if not _valid_id(kid) or not key or kid == current_id:
            continue
        try:
            keys[kid] = Fernet(key.encode())
        except Exception:
            log.warning("store token previous key ignored id=%s", kid)
    return current_id, keys


def seal(value: str) -> str:
    kid, keys = _keys()
    token = keys[kid].encrypt(value.encode()).decode()
    return f"v1.{kid}.{token}"


def open_secret(blob: Optional[str]) -> Optional[str]:
    if not blob or not blob.startswith("v1."):
        return None
    key_id, sep, token = blob[3:].partition(".")
    if not sep or not token or not _valid_id(key_id):
        return None
    fernet = _keys()[1].get(key_id)
    if fernet is None:
        return None
    try:
        return fernet.decrypt(token.encode()).decode()
    except Exception:
        log.warning("store token could not be decrypted")
        return None
