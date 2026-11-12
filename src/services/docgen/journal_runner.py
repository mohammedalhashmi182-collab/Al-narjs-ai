"""One restart-safe *internal* DocPack execution; never charges or delivers.

Called only by explicitly trusted internal code, NOT wired to a public route,
scheduler or production service. An executor can resume from the stored brief
after a crash and re-run incomplete work. All output remains internal until
a separate commercial/authorization/delivery pipeline is built.
"""
from __future__ import annotations

import asyncio
from contextlib import suppress
from uuid import UUID

from src.automation.workflow_engine import WorkflowEngine
from src.services.docgen.release_gate import independent_review
from src.services.docgen.schema import DocGenError
from src.services.docgen.team_pilot import prepare_docpack_team_preview
from src.services.service_fulfillment_journal import (
    InternalServiceJournal, JournalError, LEASE_SECONDS,
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

    # Short-lived heartbeat renewals prevent a long model call from losing
    # ownership and having two workers publish the same encrypted artifact.
    caller = asyncio.current_task()
    heartbeat = asyncio.create_task(
        _heartbeat_while_running(journal, lease, caller),
        name=f"journal-heartbeat-{job_id}",
    )
    try:
        brief, formats = await journal.request_for_lease(lease)
        checkpoints = await journal.load_step_checkpoints(lease)

        async def persist_step(step_id: str, agent_slug: str, output_data: dict) -> None:
            # Always re-run the final quality gate against the current preview.
            if agent_slug != "quality_gate":
                await journal.save_step_checkpoint(
                    lease, step_id=step_id, agent_slug=agent_slug,
                    output_data=output_data,
                )

        preview = await prepare_docpack_team_preview(
            engine,
            brief=brief,
            file_bytes=None,  # this pilot is text-brief-only and restartable
            filename=None,
            formats=formats,
            client_name="معاينة داخلية",
            restored_steps=checkpoints,
            on_step_completed=persist_step,
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
    finally:
        heartbeat.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat


async def _heartbeat_while_running(journal, lease, parent_task) -> None:
    while True:
        await asyncio.sleep(max(1, LEASE_SECONDS // 3))
        try:
            ok = await journal.heartbeat(lease)
        except Exception:
            ok = False
        if not ok:
            # A stolen, expired or unreachable lease makes this worker unsafe.
            # Cancel before it can finalize or deliver stale output.
            if parent_task is not None:
                parent_task.cancel()
            return


async def _record_failure(journal, lease, code: str) -> None:
    try:
        await journal.fail(lease, code=code)
    except JournalError:
        # A different executor may have legitimately reclaimed the lease.
        # This worker must never modify that executor's state.
        pass
