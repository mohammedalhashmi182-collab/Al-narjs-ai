"""One restart-safe *internal* DocPack execution; never charges or delivers.

Called only by explicitly trusted internal code, NOT wired to a public route,
scheduler or production service. An executor can resume from the stored brief
after a crash and re-run incomplete work. All output remains internal until
a separate commercial/authorization/delivery pipeline is built.
"""
from __future__ import annotations

from uuid import UUID

from src.automation.workflow_engine import WorkflowEngine
from src.services.docgen.release_gate import independent_review
from src.services.docgen.schema import DocGenError
from src.services.docgen.team_pilot import prepare_docpack_team_preview
from src.services.service_fulfillment_journal import (
    InternalServiceJournal, JournalError,
)


async def run_internal_docpack(
    journal: InternalServiceJournal,
    engine: WorkflowEngine,
    reviewer_provider,
    project_id: UUID,
    job_id: UUID,
) -> dict:
    """Claim -> team execution -> independent review -> encrypted persistence.

    Claiming is atomic, so one live worker can own the task; expired leases
    can be reclaimed. A provider failure blocks output instead of skipping QA.
    """
    lease = await journal.claim(project_id, job_id)
    if lease is None:
        return {"job_id": str(job_id), "status": "not_claimed"}

    try:
        brief, formats = await journal.request_for_lease(lease)
        preview = await prepare_docpack_team_preview(
            engine,
            brief=brief,
            file_bytes=None,  # this pilot is text-brief-only and restartable
            filename=None,
            formats=formats,
            client_name="معاينة داخلية",
        )
        # The team quality_gate is not enough: this must be a distinct
        # substantive review with an independent provider and exact digest.
        approval = await independent_review(preview.pack, reviewer_provider)
        filenames = await journal.approve(lease, preview.pack, approval)
        return {
            "job_id": str(job_id),
            "workflow_id": preview.workflow_id,
            "status": "reviewed",  # NOT delivered / NOT paid
            "files_stored": len(filenames),
        }
    except DocGenError:
        # Rejected QA is a terminal review hold. Never send customer content.
        await _record_failure(journal, lease, "qa_rejected")
        return {"job_id": str(job_id), "status": "review_required"}
    except JournalError:
        await _record_failure(journal, lease, "internal_error")
        return {"job_id": str(job_id), "status": "failed_or_lease_lost"}
    except Exception:
        # The details may contain tokens or personal data; do not persist
        # the exception text. A later retry may succeed after a provider outage.
        await _record_failure(journal, lease, "transient")
        return {"job_id": str(job_id), "status": "retry_scheduled"}


async def _record_failure(journal, lease, code: str) -> None:
    try:
        await journal.fail(lease, code=code)
    except JournalError:
        # A different executor may have legitimately reclaimed the lease.
        # This worker must never modify that executor's state.
        pass
