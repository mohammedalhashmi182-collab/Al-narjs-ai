"""DocPack as a runtime tool for the five agents that may deliver client files."""

from __future__ import annotations

from src.services.agent_profiles import TOOL_AGENTS
from src.services.catalog import EMPLOYEES
from src.services.docgen import DocGenError, build_docpack, parse_formats
from src.services.docgen.store import PACKS
from src.services.docgen.release_gate import ReleaseApproval, require_release

DOCPACK_AGENTS = TOOL_AGENTS["docpack"]

CONTEXT = (
    "\n\n[DocPack] هذه الأداة تبني من بيانات العميل تقريراً بصيغة PDF وملفاً بصيغة XLSX "
    "بصيغ حسابية وعرضاً بصيغة PPTX. كل رقم في الملفات محسوب في الكود من الجدول أو من "
    "الأرقام التي كتبها العميل. لا تخترع رقماً ولا تقدّر حجم سوق أو نسبة غير موجودة في البيانات.\n"
)


def allowed(slug: str) -> bool:
    return slug in DOCPACK_AGENTS


def requested(answers: dict | None) -> bool:
    """Only an explicit flag builds files during an agent run.

    A passing mention of the word report must not generate and email a pack.
    """
    if not answers:
        return False
    flag = answers.get("docpack")
    if isinstance(flag, bool):
        return flag
    if isinstance(flag, (int, float)) and not isinstance(flag, bool):
        return flag == 1
    if isinstance(flag, str) and flag.strip().lower() in {"1", "true", "yes", "on", "docpack"}:
        return True
    return False


def usable_provider(provider):
    """Skip a configured client whose fallback chain is empty (no API key).

    Calling it anyway burns the provider's retry loop and still returns nothing
    the narrative guard can keep.
    """
    if provider is None:
        return None
    chains = getattr(provider, "_fallback_chains", None)
    if isinstance(chains, dict) and not chains.get("gemini"):
        return None
    return provider


def names_for(agent_key: str) -> tuple[str, str]:
    employee = EMPLOYEES.get(agent_key) or {}
    return str(employee.get("title_ar") or agent_key), str(employee.get("title_en") or agent_key)


async def build(
    *,
    slug: str,
    brief: str = "",
    file_bytes: bytes | None = None,
    filename: str | None = None,
    formats: str | list[str] | None = None,
    model_provider=None,
    client_name: str = "",
    title_ar: str | None = None,
    title_en: str | None = None,
):
    if not allowed(slug):
        raise DocGenError("هذا الوكيل لا يصدر حزمة المستندات")
    if slug not in EMPLOYEES:
        raise DocGenError("الوكيل غير موجود")
    name_ar, name_en = names_for(slug)
    chosen = formats if isinstance(formats, list) else parse_formats(formats if isinstance(formats, str) else None)
    return await build_docpack(
        brief=brief,
        file_bytes=file_bytes,
        filename=filename,
        agent_key=slug,
        agent_name_ar=name_ar,
        agent_name_en=name_en,
        formats=chosen,
        model_provider=model_provider,
        client_name=client_name,
        title_ar=title_ar,
        title_en=title_en,
    )


def publish(
    pack, *, scope: str = "owner", project_id: str | None = None,
    approval: ReleaseApproval | None = None,
) -> dict:
    """Publish a short-lived pack. Only approved files reach customer scope."""
    if scope == "project":
        require_release(pack, approval)
    token = PACKS.put(pack.files, scope=scope, project_id=project_id)
    return {
        "id": token,
        "agent_key": pack.meta.agent_key,
        "narrative_source": pack.narrative.source,
        "files": [
            {
                "format": item.format,
                "filename": item.filename,
                "url": f"/api/docpack/files/{token}/{item.filename}",
                "label_ar": item.label_ar,
                "label_en": item.label_en,
                "media_type": item.media_type,
            }
            for item in pack.files
        ],
        "facts": summary_facts(pack),
    }


def summary_facts(pack) -> list[dict]:
    """The compact fact list returned to the caller. Source cells stay in the files."""
    rows = []
    for fact in pack.analysis.facts:
        keep = fact.key in {"row_count", "column_count", "growth_pct", "forecast_next"}
        keep = keep or fact.kind == "total"
        keep = keep or (
            fact.kind == "average"
            and pack.analysis.primary_metric
            and fact.key == f"average:{pack.analysis.primary_metric}"
        )
        if keep:
            rows.append({
                "label_ar": fact.label_ar,
                "label_en": fact.label_en,
                "value": fact.display,
                "kind": fact.kind,
            })
    return rows


async def email_pack(to: str, pack, *, approval: ReleaseApproval | None = None) -> bool:
    # No proof => no send, including legacy src/main.py callers.
    require_release(pack, approval)
    if not to:
        return False
    # Legacy agent-generated packs also must pass artifact integrity checks
    # before attempting email. This does NOT replace an independent review of
    # substantive content or customer authorization.
    from src.services.docgen.team_pilot import verify_pack_files
    verify_pack_files(pack, [item.format for item in pack.files])
    from src.services import email_service

    lines = [f"{fact.label_ar}: {fact.display}" for fact in pack.analysis.facts if fact.kind == "total"]
    growth = next((fact for fact in pack.analysis.facts if fact.key == "growth_pct"), None)
    forecast = next((fact for fact in pack.analysis.facts if fact.key == "forecast_next"), None)
    if growth:
        lines.append(f"{growth.label_ar}: {growth.display}")
    if forecast:
        lines.append(f"{forecast.label_ar}: {forecast.display}")
    body = (
        f"مرفق حزمة المستندات من {pack.meta.agent_name_ar}.\n"
        "الأرقام محسوبة من البيانات، وملف إكسل يحتوي الصيغ.\n\n"
        + ("\n".join(lines) + "\n\n" if lines else "")
        + "— النرجس للذكاء الاصطناعي"
    )
    attachments = [(item.filename, item.content, item.media_type) for item in pack.files]
    return bool(await email_service.send_email(
        to,
        f"حزمة مستندات من {pack.meta.agent_name_ar} — النرجس",
        body,
        attachments=attachments,
    ))
