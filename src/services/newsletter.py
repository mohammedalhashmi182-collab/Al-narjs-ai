"""Newsletter subscriptions (popup on the public site).

The ``newsletter_subscribers`` table lives on its OWN MetaData, not on
``Base``: startup ``create_all`` must not create it. Schema changes need the
owner's approval, so the table arrives through the reviewed migration in
review-packs/site-pack-newsletter-migration.patch (alembic 0018). Until it
exists the endpoint fails closed (503) and the popup stays hidden: nothing
is ever accepted that cannot be stored, and no fake success is shown.

Stored per row: the e-mail (lower-cased), the consent text version and time,
the page language and a salted hash of the IP (never the raw IP).
"""

from __future__ import annotations

import hashlib
import re
import time

import sqlalchemy as sa

TABLE_NAME = "newsletter_subscribers"
CONSENT_VERSION = "nl-2026-10"
CONSENT_AR = "أوافق على استلام النشرة ويمكنني إلغاء الاشتراك في أي وقت وفق سياسة الخصوصية"
CONSENT_EN = (
    "I agree to receive the newsletter and can unsubscribe at any time "
    "under the privacy policy"
)
UNAVAILABLE_AR = "الاشتراك في النشرة غير متاح حالياً. نعتذر، جرّب لاحقاً."
UNAVAILABLE_EN = "Newsletter sign-up is not available right now. Please try again later."

metadata = sa.MetaData()
subscribers = sa.Table(
    TABLE_NAME,
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("email", sa.String(254), nullable=False, unique=True),
    sa.Column("lang", sa.String(2), nullable=False, server_default="ar"),
    sa.Column("consent_version", sa.String(20), nullable=False),
    sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ip_hash", sa.String(32), nullable=True),
    sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)

# Pragmatic RFC 5322 subset: one @, a dotted domain, no spaces or control chars.
_EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")

_cache: dict[str, float | bool] = {"ok": False, "at": 0.0}
_CACHE_SECONDS = 60.0


def normalize_email(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    email = raw.strip().lower()
    if len(email) > 254 or ".." in email or not _EMAIL_RE.match(email):
        return None
    return email


def ip_hash(ip: str, secret: str) -> str:
    return hashlib.sha256(f"{secret}:newsletter:{ip}".encode()).hexdigest()[:32]


def reset_cache() -> None:
    _cache["ok"] = False
    _cache["at"] = 0.0


async def table_ready(engine) -> bool:
    """True only when the reviewed migration has created the table.

    A positive answer is cached for a minute; a negative one is re-checked on
    every call so the endpoint opens as soon as the migration runs.
    """
    now = time.monotonic()
    if _cache["ok"] and now - float(_cache["at"]) < _CACHE_SECONDS:
        return True
    try:
        async with engine.connect() as conn:
            exists = await conn.run_sync(lambda c: sa.inspect(c).has_table(TABLE_NAME))
    except Exception:  # noqa: BLE001  DB down = closed, never a fake success
        exists = False
    _cache["ok"] = bool(exists)
    _cache["at"] = now
    return bool(exists)


async def subscribe(engine, *, email: str, lang: str, iphash: str | None) -> str:
    """Insert or re-activate a subscriber. Returns 'created' or 'exists'."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    async with engine.begin() as conn:
        row = (
            await conn.execute(
                sa.select(subscribers.c.id, subscribers.c.unsubscribed_at).where(subscribers.c.email == email)
            )
        ).first()
        if row is not None:
            if row.unsubscribed_at is not None:
                await conn.execute(
                    subscribers.update()
                    .where(subscribers.c.id == row.id)
                    .values(unsubscribed_at=None, consent_version=CONSENT_VERSION, consent_at=now, lang=lang)
                )
                return "created"
            return "exists"
        try:
            async with conn.begin_nested():  # savepoint: a lost race must not abort the outer transaction
                await conn.execute(
                    subscribers.insert().values(
                        email=email, lang=lang, consent_version=CONSENT_VERSION, consent_at=now, ip_hash=iphash
                    )
                )
        except sa.exc.IntegrityError:
            return "exists"  # concurrent duplicate
    return "created"
