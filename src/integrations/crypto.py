"""Fernet for store tokens. Never derived from ``SECRET_KEY``.

Ciphertext is ``v1.<key id>.<fernet token>``.

* ``STORE_TOKEN_ENC_KEY`` — urlsafe-base64 Fernet key. Required. The integration
  stays off while this is empty or not a Fernet key.
* ``STORE_TOKEN_ENC_KEY_ID`` — id written into new ciphertext (default ``1``).
* ``STORE_TOKEN_ENC_PREVIOUS_KEYS`` — comma-separated ``id:key`` pairs, decrypt only.

To rotate, put the old ``id:key`` in ``STORE_TOKEN_ENC_PREVIOUS_KEYS`` and point
``STORE_TOKEN_ENC_KEY`` / ``STORE_TOKEN_ENC_KEY_ID`` at the new key. Refresh
re-seals with the current key. Rotating ``SECRET_KEY`` does not affect these tokens.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from src.integrations.config import env

log = logging.getLogger(__name__)

_ID = re.compile(r"[A-Za-z0-9_-]{1,16}")


class StoreTokenKeyError(RuntimeError):
    """``STORE_TOKEN_ENC_KEY`` is missing or not a Fernet key."""


def _valid_id(value: str) -> bool:
    return bool(_ID.fullmatch(value or ""))


def _load() -> Optional[tuple[str, dict]]:
    from cryptography.fernet import Fernet

    material = env("STORE_TOKEN_ENC_KEY")
    if not material:
        return None
    current_id = env("STORE_TOKEN_ENC_KEY_ID") or "1"
    if not _valid_id(current_id):
        current_id = "1"
    try:
        current = Fernet(material.encode())
    except Exception:
        log.warning("store token key rejected")
        return None
    keys = {current_id: current}
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


def key_ready() -> bool:
    return _load() is not None


def seal(value: str) -> str:
    loaded = _load()
    if loaded is None:
        raise StoreTokenKeyError("STORE_TOKEN_ENC_KEY is required")
    kid, keys = loaded
    token = keys[kid].encrypt(value.encode()).decode()
    return f"v1.{kid}.{token}"


def open_secret(blob: Optional[str]) -> Optional[str]:
    loaded = _load()
    if loaded is None or not blob or not blob.startswith("v1."):
        return None
    key_id, sep, token = blob[3:].partition(".")
    if not sep or not token or not _valid_id(key_id):
        return None
    fernet = loaded[1].get(key_id)
    if fernet is None:
        return None
    try:
        return fernet.decrypt(token.encode()).decode()
    except Exception:
        log.warning("store token could not be decrypted")
        return None
