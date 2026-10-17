"""Single-use OAuth state bound to the portal session that started the install.

The signed state carries the nonce. The row stores which project and which
session kind (merchant portal cookie, or the owner console) may finish the
callback, plus the portal token version at issue time. A callback with no
matching session, a different project, a revoked version, or a reused nonce
does not exchange the code.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import update

_TTL = timedelta(minutes=10)


def _version(project) -> int:
    return int(getattr(project, "portal_token_version", 0) or 0)


def _aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment


def issue_kind(request, project) -> tuple[str, int]:
    """Which authenticated session is starting the install."""
    from src.core.owner_auth import check_owner
    from src.core.portal_auth import session_claims, session_valid_for

    claims = session_claims(request)
    if session_valid_for(claims, project):
        return "portal", int(claims.get("v", _version(project)))
    if check_owner(request):
        return "owner", _version(project)
    from fastapi import HTTPException

    raise HTTPException(401, "Portal login required")


async def issue_nonce(session, request, project, platform: str) -> str:
    from src.models.store_integration import StoreOAuthNonce

    kind, version = issue_kind(request, project)
    nonce = secrets.token_urlsafe(24)
    session.add(StoreOAuthNonce(
        nonce=nonce,
        project_id=project.id,
        platform=platform,
        portal_token_version=version,
        auth_kind=kind,
        expires_at=datetime.now(UTC) + _TTL,
    ))
    await session.flush()
    return nonce


def _matches(request, project, row) -> bool:
    from src.core.owner_auth import check_owner
    from src.core.portal_auth import session_claims, session_valid_for

    if int(row.portal_token_version or 0) != _version(project):
        return False
    if row.auth_kind == "owner":
        return check_owner(request)
    return session_valid_for(session_claims(request), project)


async def claim_nonce(session, request, project, nonce: str, platform: str) -> bool:
    """Mark the nonce used inside the current transaction. False if it cannot be claimed."""
    from src.models.store_integration import StoreOAuthNonce

    if not nonce or project is None:
        return False
    row = await session.get(StoreOAuthNonce, nonce)
    if row is None or row.used_at is not None:
        return False
    if row.project_id != project.id or row.platform != platform:
        return False
    if row.expires_at is None or _aware(row.expires_at) <= datetime.now(UTC):
        return False
    if not _matches(request, project, row):
        return False
    session.expunge(row)
    result = await session.execute(
        update(StoreOAuthNonce)
        .where(StoreOAuthNonce.nonce == nonce, StoreOAuthNonce.used_at.is_(None))
        .values(used_at=datetime.now(UTC))
        .returning(StoreOAuthNonce.nonce),
        execution_options={"synchronize_session": False},
    )
    return result.scalar_one_or_none() is not None
