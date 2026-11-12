"""Internal DocPack pilot: collaborative agents + deterministic file QA, no delivery.

This is deliberately an *unpublished preview*. A verified, accepted offer,
authoritative payment, durable storage and tenant authorization are separate
release gates. Do NOT call this directly from public HTTP routes.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from zipfile import BadZipFile, ZipFile

from src.automation.workflow_engine import WorkflowDefinition, WorkflowEngine, WorkflowStep
from src.services.docgen.pipeline import build_docpack
from src.services.docgen.schema import DocGenError, DocPack


@dataclass(frozen=True)
class FileEvidence:
    name: str
    format: str
    size: int
    sha256: str


@dataclass
class PreparedPreview:
    """In-memory result for a trusted reviewer only; NOT customer delivery."""

    pack: DocPack
    workflow_id: str
    files: list[FileEvidence]
    quality_passed: bool = True


_EXPECTED_CONTENT = {
    "xlsx": "xl/workbook.xml",
    "pptx": "ppt/presentation.xml",
    "docx": "word/document.xml",
}
_MAX_FILE_BYTES = 20 * 1024 * 1024
_MAX_UNCOMPRESSED_BYTES = 60 * 1024 * 1024


def verify_pack_files(pack: DocPack, requested_formats: list[str]) -> list[FileEvidence]:
    """Independently check formats, archive structure and content before release."""
    files = pack.files
    if not files or len(files) != len(requested_formats):
        raise DocGenError("DocPack QA: missing or unexpected deliverable")
    if len(set(requested_formats)) != len(requested_formats):
        raise DocGenError("DocPack QA: duplicate format requested")
    if {item.format for item in files} != set(requested_formats):
        raise DocGenError("DocPack QA: file types do not match the request")
    if len({item.filename for item in files}) != len(files):
        raise DocGenError("DocPack QA: duplicate output filename")

    evidence = []
    for item in files:
        data = item.content
        if not data or len(data) > _MAX_FILE_BYTES or not item.filename.endswith("." + item.format):
            raise DocGenError("DocPack QA: invalid file name, size or content")
        if item.format == "pdf":
            if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-2048:]:
                raise DocGenError("DocPack QA: invalid PDF")
        elif item.format in _EXPECTED_CONTENT:
            try:
                with ZipFile(BytesIO(data)) as archive:
                    members = archive.namelist()
                    if archive.testzip() is not None or archive.comment:
                        raise DocGenError("DocPack QA: corrupt archive")
                    if "[Content_Types].xml" not in members or _EXPECTED_CONTENT[item.format] not in members:
                        raise DocGenError("DocPack QA: incomplete office file")
                    if any(
                        name.startswith("/") or ".." in name.split("/")
                        for name in members
                    ):
                        raise DocGenError("DocPack QA: unsafe archive path")
                    if sum(part.file_size for part in archive.infolist()) > _MAX_UNCOMPRESSED_BYTES:
                        raise DocGenError("DocPack QA: expanded archive too large")
            except (BadZipFile, ValueError, OSError) as exc:
                raise DocGenError("DocPack QA: invalid office archive") from exc
        else:
            raise DocGenError("DocPack QA: unknown output format")
        evidence.append(FileEvidence(item.filename, item.format, len(data), sha256(data).hexdigest()))
    return evidence


def _team_definition() -> WorkflowDefinition:
    # Two independent specialists start together. A different specialist
    # reviews both; WorkflowEngine refuses to complete when its verdict fails.
    return WorkflowDefinition(
        global_config={"slug": "docpack-team-internal-preview"},
        steps=[
            WorkflowStep(id="analysis", agent_slug="data_analyst"),
            WorkflowStep(id="plan", agent_slug="project_manager"),
            WorkflowStep(id="review", agent_slug="quality_gate", depends_on=["analysis", "plan"]),
        ],
    )


async def prepare_docpack_team_preview(
    engine: WorkflowEngine,
    *,
    brief: str,
    file_bytes: bytes | None = None,
    filename: str | None = None,
    formats: list[str] | None = None,
    client_name: str = "عميل تجريبي",
) -> PreparedPreview:
    """Build files locally, coordinate specialists, then hold for owner review.

    No invoices, external messages, customer download tokens or durable state.
    This is a testable building block, *not* a paid service or a production API.
    """
    chosen = formats if formats is not None else ["pdf", "xlsx", "pptx"]
    if not chosen or any(fmt not in {"pdf", "xlsx", "pptx", "docx"} for fmt in chosen):
        raise DocGenError("DocPack QA: unsupported output formats")
    if not (brief or "").strip() and not file_bytes:
        raise DocGenError("DocPack QA: missing client brief or data")

    pack = await build_docpack(
        brief=brief, file_bytes=file_bytes, filename=filename,
        agent_key="data_analyst", agent_name_ar="محلل البيانات",
        agent_name_en="Data Analyst", formats=chosen, model_provider=None,
        client_name=client_name,
    )
    # Check file structure before spending agent tokens or making any preview
    # available to a caller. Evidence alone is not permission to deliver.
    evidence = verify_pack_files(pack, chosen)
    facts = [
        {"key": f.key, "value": f.display, "kind": f.kind}
        for f in pack.analysis.facts
    ]
    objective = (brief or "").strip() or "تحليل الملف المرفق وإعداد حزمة مستندات"
    result = await engine.execute(_team_definition(), {
        "client_request": objective,
        "locale": "ar",
        "data": str(facts),
        "context": "Facts are derived by deterministic DocPack code; no external market assumptions.",
        "questions": objective,
        "tasks": objective,
        "team_size": "3",
        "timeline": "internal preview only; do not promise delivery",
        "dependencies": "analysis and plan run in parallel, then independent review",
        "priority": "accuracy and matching source data",
        "objective": objective,
        "agent_code": "TEAM",
        "agent_name": "DocPack team",
        "brand_voice": "Arabic-first, professional, Saudi market, evidence-grounded",
    })
    if not result.success:
        raise DocGenError(f"DocPack team or quality review failed: {result.error}")
    review = result.final_context.get("review") or {}
    if "PASS" not in str(review.get("content", "")).upper():
        raise DocGenError("DocPack QA: reviewer approval missing")
    return PreparedPreview(
        pack=pack, workflow_id=str(result.workflow_id), files=evidence
    )
