"""Durable *internal-only* service work ledger, without any payment or outbound I/O.

This module is deliberately not a public endpoint or an automatic worker.
It persists work in the existing database, uses DB-atomic claims, survives
process restarts, and stores encrypted, quality-approved artifacts. It does
not imply an accepted commercial agreement, a settled payment or permission
to send files externally.

An internal development executor must provide a Fernet key through the
NARJIS_ARTIFACT_FERNET_KEY environment variable; no implicit fallback to
SECRET_KEY or a generated volatile key.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError

from src.models import ClientProject
from src.models.service_delivery import (
    ServiceArtifact,
    ServiceJob,
    ServiceJournalEvent,
    ServiceOffer,
    ServiceStepCheckpoint,
)
from src.services.docgen.release_gate import ReleaseApproval, require_release
from src.services.docgen.schema import DocGenError, DocPack
from src.services.docgen.team_pilot import verify_pack_files

# Small bounded blobs protect a 512-MB web instance and avoid rapidly filling
# the current database. Large files need separately reviewed object storage.
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 10 * 1024 * 1024
LEASE_SECONDS = 120
RETRY_BASE_SECONDS = 20
RETRY_MAX_SECONDS = 600
_IDEMPOTENCY = re.compile(r"^[A-Za-z0-9_-]{8,100}$")
_ALLOWED_FORMATS = frozenset({"pdf", "xlsx", "pptx", "docx"})
_ERROR_CODES = frozenset({"agent_unavailable", "qa_rejected", "timeout", "transient", "internal_error"})
_CHECKPOINT_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")
_MAX_CHECKPOINT_BYTES = 48 * 1024


class JournalError(ValueError):
    """The requested durable state transition is not allowed."""


@dataclass(frozen=True)
class Lease:
    job_id: UUID
    project_id: UUID
    token: str
    attempt: int
    expires_at: datetime


def _key() -> Fernet:
    raw = (os.getenv("NARJIS_ARTIFACT_FERNET_KEY") or "").strip()
    if not raw:
        raise JournalError("Artifact encryption key is not configured")
    try:
        return Fernet(raw.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise JournalError("Invalid artifact encryption key") from exc


def _now(value: datetime | None = None) -> datetime:
    value = value or datetime.now(UTC)
    if value.tzinfo is None:
        raise JournalError("A timezone-aware timestamp is required")
    return value.astimezone(UTC)


def _aware(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


def _brief_digest(brief: str, formats: list[str]) -> str:
    return hashlib.sha256((brief + "\n" + ",".join(formats)).encode("utf-8")).hexdigest()


def _event(job: ServiceJob, name: str, key: str, **evidence: int | str | bool) -> ServiceJournalEvent:
    # Never write the original request, model output, customer identity or file bytes to journal evidence.
    return ServiceJournalEvent(
        job_id=job.id, project_id=job.project_id,
        event_key=f"{job.id}:{key}", event_name=name, evidence=evidence,
    )


class InternalServiceJournal:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        # Each process commits small checkpoints in order. SQLite's single
        # shared test connection cannot commit two sessions simultaneously;
        # PostgreSQL also benefits from avoiding excess same-job contention.
        self._checkpoint_lock = asyncio.Lock()

    async def create_preview(
        self,
        project_id: UUID,
        *,
        request_key: str,
        brief: str,
        formats: list[str],
    ) -> UUID:
        """Idempotently enqueue one internal work request, never send or charge.

        Reusing a request key with changed scope fails instead of silently
        turning a preview into a different customer's or project's work.
        """
        crypt = _key()  # Fail closed before modifying any records.
        if not isinstance(request_key, str) or not _IDEMPOTENCY.fullmatch(request_key):
            raise JournalError("Invalid request idempotency key")
        if not isinstance(brief, str) or not 1 <= len(brief.strip()) <= 4000:
            raise JournalError("Brief must contain 1–4000 characters")
        brief = brief.strip()
        if (not isinstance(formats, list) or not formats or len(formats) > 4
                or len(set(formats)) != len(formats)
                or any(fmt not in _ALLOWED_FORMATS for fmt in formats)):
            raise JournalError("Unsupported or repeated document formats")
        formats = sorted(formats)
        digest = _brief_digest(brief, formats)

        async with self.session_factory() as session:
            project = await session.get(ClientProject, project_id)
            if project is None:
                raise JournalError("Unknown project")
            previous = (await session.execute(select(ServiceJob, ServiceOffer).join(
                ServiceOffer, ServiceOffer.id == ServiceJob.offer_id
            ).where(
                ServiceJob.project_id == project_id,
                ServiceJob.idempotency_key == request_key,
            ))).first()
            if previous:
                if previous[1].digest != digest:
                    raise JournalError("Idempotency key reused with different work")
                return previous[0].id

            offer = ServiceOffer(
                project_id=project_id, service_slug="docpack",
                brief_encrypted=crypt.encrypt(brief.encode("utf-8")),
                formats=formats, scope={"mode": "internal_preview"},
                terms_version="internal-preview-v1", digest=digest,
            )
            session.add(offer)
            try:
                await session.flush()
                job = ServiceJob(
                    offer_id=offer.id, project_id=project_id,
                    idempotency_key=request_key, status="queued", max_attempts=3,
                )
                session.add(job)
                await session.flush()
                session.add(_event(job, "queued", "queued", scope="internal_preview"))
                await session.commit()
            except IntegrityError:
                await session.rollback()
                # Database unique constraints also guard concurrent creates.
                existing = (await session.execute(select(ServiceJob, ServiceOffer).join(
                    ServiceOffer, ServiceOffer.id == ServiceJob.offer_id
                ).where(
                    ServiceJob.project_id == project_id,
                    ServiceJob.idempotency_key == request_key,
                ))).first()
                if existing and existing[1].digest == digest:
                    return existing[0].id
                raise JournalError("Conflicting request key") from None
            return job.id

    async def claim(
        self, project_id: UUID, job_id: UUID, *, now: datetime | None = None
    ) -> Lease | None:
        """Atomic lease: safe for concurrent workers and stale-lease reclaim."""
        at = _now(now)
        expiry = at + timedelta(seconds=LEASE_SECONDS)
        token = secrets.token_hex(24)
        active = or_(
            and_(ServiceJob.status == "queued",
                 or_(ServiceJob.next_attempt_at.is_(None), ServiceJob.next_attempt_at <= at)),
            and_(ServiceJob.status == "running", ServiceJob.leased_until <= at),
        )
        async with self.session_factory() as session:
            result = await session.execute(
                update(ServiceJob).where(
                    ServiceJob.id == job_id,
                    ServiceJob.project_id == project_id,
                    ServiceJob.attempts < ServiceJob.max_attempts,
                    active,
                ).values(
                    status="running", lease_token=token, leased_until=expiry,
                    attempts=ServiceJob.attempts + 1, version=ServiceJob.version + 1,
                    next_attempt_at=None, last_error=None,
                ).returning(ServiceJob)
            )
            job = result.scalar_one_or_none()
            if job is None:
                # An abandoned third attempt must not remain "running"
                # forever just because it can no longer be re-claimed.
                exhausted = await session.execute(
                    update(ServiceJob).where(
                        ServiceJob.id == job_id,
                        ServiceJob.project_id == project_id,
                        ServiceJob.status == "running",
                        ServiceJob.leased_until <= at,
                        ServiceJob.attempts >= ServiceJob.max_attempts,
                    ).values(
                        status="failed_final", lease_token=None, leased_until=None,
                        last_error="timeout", version=ServiceJob.version + 1,
                    ).returning(ServiceJob)
                )
                failed = exhausted.scalar_one_or_none()
                if failed:
                    session.add(_event(
                        failed, "failed_final", "lease-exhausted", attempt=failed.attempts,
                        code="timeout",
                    ))
                    await session.commit()
                else:
                    await session.rollback()
                return None
            session.add(_event(job, "claimed", f"attempt-{job.attempts}", attempt=job.attempts))
            await session.commit()
            return Lease(job.id, project_id, token, job.attempts, expiry)

    async def request_for_lease(
        self, lease: Lease, *, now: datetime | None = None
    ) -> tuple[str, list[str]]:
        """Decrypt a scoped brief and get its formats for this one active executor."""
        crypt = _key()
        at = _now(now)
        async with self.session_factory() as session:
            row = (await session.execute(select(ServiceJob, ServiceOffer).join(
                ServiceOffer, ServiceOffer.id == ServiceJob.offer_id
            ).where(ServiceJob.id == lease.job_id, ServiceJob.project_id == lease.project_id))
            ).first()
            if not row or row[0].status != "running" or row[0].lease_token != lease.token:
                raise JournalError("Not the active job lease")
            if not row[0].leased_until or _aware(row[0].leased_until) <= at:
                raise JournalError("The job lease has expired")
            try:
                brief = crypt.decrypt(row[1].brief_encrypted).decode("utf-8")
            except (InvalidToken, UnicodeError) as exc:
                raise JournalError("Encrypted brief cannot be verified") from exc
            return brief, list(row[1].formats)

    async def brief_for_lease(self, lease: Lease, *, now: datetime | None = None) -> str:
        """Compatibility helper for workers that only need the task text."""
        brief, _ = await self.request_for_lease(lease, now=now)
        return brief

    async def heartbeat(self, lease: Lease, *, now: datetime | None = None) -> bool:
        at = _now(now)
        async with self.session_factory() as session:
            res = await session.execute(update(ServiceJob).where(
                ServiceJob.id == lease.job_id,
                ServiceJob.project_id == lease.project_id,
                ServiceJob.status == "running",
                ServiceJob.lease_token == lease.token,
                ServiceJob.leased_until > at,
            ).values(
                leased_until=at + timedelta(seconds=LEASE_SECONDS),
                version=ServiceJob.version + 1,
            ))
            await session.commit()
            return res.rowcount == 1

    async def fail(
        self, lease: Lease, *,
        code: str,
        now: datetime | None = None,
    ) -> str:
        """Retry transient errors with bounded backoff. No exception text in DB."""
        if code not in _ERROR_CODES:
            raise JournalError("Invalid sanitized failure code")
        at = _now(now)
        async with self.session_factory() as session:
            job = (await session.execute(
                select(ServiceJob).where(
                    ServiceJob.id == lease.job_id, ServiceJob.project_id == lease.project_id
                ).with_for_update()
            )).scalar_one_or_none()
            if (job is None or job.status != "running" or job.lease_token != lease.token
                    or not job.leased_until or _aware(job.leased_until) <= at):
                raise JournalError("Lease lost; cannot fail this job")
            final = job.attempts >= job.max_attempts or code == "qa_rejected"
            job.status = "failed_final" if final else "queued"
            job.next_attempt_at = None if final else at + timedelta(
                seconds=min(RETRY_MAX_SECONDS, RETRY_BASE_SECONDS * (2 ** (job.attempts - 1)))
            )
            job.last_error = code
            job.lease_token = None
            job.leased_until = None
            job.version += 1
            session.add(_event(job, "failed_final" if final else "retry_scheduled",
                               f"failure-{job.attempts}", attempt=job.attempts, code=code))
            await session.commit()
            return job.status

    async def save_step_checkpoint(
        self, lease: Lease, *, step_id: str, agent_slug: str, output_data: dict,
        now: datetime | None = None,
    ) -> str:
        async with self._checkpoint_lock:
            return await self._save_step_checkpoint_locked(
                lease, step_id=step_id, agent_slug=agent_slug,
                output_data=output_data, now=now,
            )

    async def _save_step_checkpoint_locked(
        self, lease: Lease, *, step_id: str, agent_slug: str, output_data: dict,
        now: datetime | None = None,
    ) -> str:
        """Persist one fully completed agent result before the engine marks it done.

        Encrypted bytes are scoped to the current project and active lease.
        An old worker cannot overwrite or add results after its lease expires.
        """
        import json

        if (not isinstance(step_id, str) or not _CHECKPOINT_NAME.fullmatch(step_id)
                or not isinstance(agent_slug, str) or not _CHECKPOINT_NAME.fullmatch(agent_slug)):
            raise JournalError("Invalid checkpoint step or agent")
        if not isinstance(output_data, dict) or not isinstance(output_data.get("content"), str):
            raise JournalError("Checkpoint must contain a text result")
        try:
            raw = json.dumps({
                "content": output_data["content"],
                "structured_output": output_data.get("structured_output"),
                "tokens_used": output_data.get("tokens_used", 0),
                "quality": output_data.get("quality", {}),
            }, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise JournalError("Checkpoint result is not JSON-serializable") from exc
        if len(raw) > _MAX_CHECKPOINT_BYTES:
            raise JournalError("Checkpoint exceeds safe storage limit")
        crypt = _key()
        digest = hashlib.sha256(raw).hexdigest()
        at = _now(now)
        async with self.session_factory() as session:
            job = (await session.execute(
                select(ServiceJob).where(
                    ServiceJob.id == lease.job_id,
                    ServiceJob.project_id == lease.project_id,
                ).with_for_update()
            )).scalar_one_or_none()
            if (not job or job.status != "running" or job.lease_token != lease.token
                    or not job.leased_until or _aware(job.leased_until) <= at):
                raise JournalError("Active lease required for checkpoint")
            previous = (await session.execute(select(ServiceStepCheckpoint).where(
                ServiceStepCheckpoint.job_id == lease.job_id,
                ServiceStepCheckpoint.project_id == lease.project_id,
                ServiceStepCheckpoint.step_id == step_id,
            ))).scalar_one_or_none()
            if previous is not None:
                if previous.agent_slug != agent_slug or previous.content_sha256 != digest:
                    raise JournalError("Checkpoint conflict: previously committed result differs")
                return digest
            session.add(ServiceStepCheckpoint(
                job_id=lease.job_id, project_id=lease.project_id, step_id=step_id,
                agent_slug=agent_slug, encrypted_output=crypt.encrypt(raw), content_sha256=digest,
            ))
            session.add(_event(job, "step_completed", f"step-{step_id}",
                               step=step_id, sha256=digest))
            await session.commit()
            return digest

    async def load_step_checkpoints(self, lease: Lease) -> dict[str, dict]:
        """Load only verified completed steps for a freshly claimed lease."""
        import json

        await self.request_for_lease(lease)  # Revalidate tenant + active lease.
        crypt = _key()
        async with self.session_factory() as session:
            checkpoints = (await session.execute(select(ServiceStepCheckpoint).where(
                ServiceStepCheckpoint.job_id == lease.job_id,
                ServiceStepCheckpoint.project_id == lease.project_id,
            ))).scalars().all()
        restored: dict[str, dict] = {}
        for checkpoint in checkpoints:
            try:
                raw = crypt.decrypt(checkpoint.encrypted_output)
                if hashlib.sha256(raw).hexdigest() != checkpoint.content_sha256:
                    raise JournalError("Checkpoint checksum mismatch")
                data = json.loads(raw)
                if not isinstance(data, dict) or not isinstance(data.get("content"), str):
                    raise JournalError("Malformed step checkpoint")
                restored[checkpoint.step_id] = {
                    "agent_slug": checkpoint.agent_slug,
                    "output_data": data,
                }
            except (InvalidToken, UnicodeError, ValueError, TypeError) as exc:
                raise JournalError("Cannot authenticate saved workflow checkpoint") from exc
        return restored

    async def approve(
        self, lease: Lease, pack: DocPack, approval: ReleaseApproval, *,
        now: datetime | None = None,
    ) -> list[str]:
        """Save encrypted artifacts after a matching, independent QA approval.

        No public download or email is generated here; a separate commercial
        release gate is required before *any* customer-facing delivery.
        """
        crypt = _key()
        require_release(pack, approval)
        file_evidence = verify_pack_files(pack, [item.format for item in pack.files])
        if not file_evidence or len(pack.files) > 4:
            raise JournalError("Invalid artifact count")
        if (any(len(item.content) > MAX_FILE_BYTES for item in pack.files)
                or sum(len(item.content) for item in pack.files) > MAX_TOTAL_BYTES):
            raise JournalError("Artifact exceeds bounded storage limits")
        at = _now(now)
        async with self.session_factory() as session:
            row = (await session.execute(select(ServiceJob, ServiceOffer).join(
                ServiceOffer, ServiceOffer.id == ServiceJob.offer_id
            ).where(
                ServiceJob.id == lease.job_id, ServiceJob.project_id == lease.project_id
            ).with_for_update())).first()
            if not row:
                raise JournalError("Unknown job for this project")
            job, offer = row
            if (job.status != "running" or job.lease_token != lease.token
                    or not job.leased_until or _aware(job.leased_until) <= at):
                raise JournalError("Lease lost; approval is not allowed")
            if sorted(item.format for item in pack.files) != sorted(offer.formats):
                raise JournalError("Artifact types differ from the request")
            try:
                original = crypt.decrypt(offer.brief_encrypted).decode("utf-8")
            except (InvalidToken, UnicodeError) as exc:
                raise JournalError("Encrypted request cannot be verified") from exc
            if pack.meta.brief.strip() != original:
                raise JournalError("Approved content does not match customer brief")
            for item in pack.files:
                session.add(ServiceArtifact(
                    job_id=job.id, project_id=lease.project_id,
                    filename=item.filename, media_type=item.media_type,
                    sha256=hashlib.sha256(item.content).hexdigest(),
                    byte_count=len(item.content),
                    encrypted_bytes=crypt.encrypt(item.content),
                ))
            job.status = "reviewed"
            job.qa_digest = approval.digest
            job.lease_token = None
            job.leased_until = None
            job.version += 1
            session.add(_event(job, "reviewed", "reviewed",
                               file_count=len(file_evidence),
                               total_bytes=sum(item.size for item in file_evidence)))
            await session.commit()
            return [item.filename for item in pack.files]

    async def read_reviewed_artifact(
        self, project_id: UUID, job_id: UUID, filename: str,
    ) -> bytes | None:
        """Internal authorized read; not a public bearer-token download API."""
        crypt = _key()
        async with self.session_factory() as session:
            row = (await session.execute(select(ServiceArtifact).join(
                ServiceJob, ServiceJob.id == ServiceArtifact.job_id
            ).where(
                ServiceArtifact.project_id == project_id,
                ServiceJob.project_id == project_id,
                ServiceJob.id == job_id,
                ServiceJob.status == "reviewed",
                ServiceArtifact.filename == filename,
            ))).scalar_one_or_none()
            if row is None:
                return None
            try:
                data = crypt.decrypt(row.encrypted_bytes)
            except InvalidToken as exc:
                raise JournalError("Artifact integrity verification failed") from exc
            if len(data) != row.byte_count or hashlib.sha256(data).hexdigest() != row.sha256:
                raise JournalError("Artifact hash verification failed")
            return data

    async def project_status(self, project_id: UUID, *, limit: int = 30) -> list[dict]:
        """Sanitized status for a trusted owner or a separately-authenticated portal."""
        async with self.session_factory() as session:
            rows = (await session.execute(select(ServiceJob).where(
                ServiceJob.project_id == project_id
            ).order_by(ServiceJob.created_at.desc()).limit(max(1, min(limit, 100))))).scalars()
            return [{
                "id": str(job.id), "status": job.status, "attempts": job.attempts,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            } for job in rows]
