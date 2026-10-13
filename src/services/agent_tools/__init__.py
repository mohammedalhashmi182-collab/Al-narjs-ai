"""Tools the specialist agents can use. Everything here is read-only towards the
outside world: web search and store connectors only fetch; nothing is sent or
posted on anyone's behalf. Missing credentials disable a tool with a clear
message instead of failing the agent run."""

from src.services.agent_tools import data_files, knowledge_base, store_connectors, web_search  # noqa: F401

# Which agents get which tool context injected into their run.
WEB_SEARCH_AGENTS = frozenset({"market_analyst", "competitor_analyst", "data_analyst", "search_discovery", "business_ideas"})
DATA_FILE_AGENTS = frozenset({"data_analyst"})
STORE_AGENTS = frozenset({"store_manager"})
KNOWLEDGE_AGENTS = frozenset({"customer_service", "customer_manager"})


def status() -> dict:
    """Configuration status for the owner console (never includes secret values)."""
    return {
        "web_search": web_search.status(),
        "stores": store_connectors.status(),
        "data_files": {"enabled": True, "max_bytes": data_files.MAX_UPLOAD_BYTES, "types": list(data_files.ALLOWED)},
        "knowledge_base": {"enabled": True, "max_bytes": knowledge_base.MAX_UPLOAD_BYTES, "types": ["text", "pdf"]},
    }


def _query_from(answers: dict | None, client_name: str | None) -> str:
    vals = [str(v) for v in (answers or {}).values() if isinstance(v, (str, int, float)) and str(v).strip()]
    q = " ".join(vals)[:250]
    return q or (client_name or "")


async def run_context(session, slug: str, project, answers: dict | None) -> str:
    """Extra prompt context from the tools this agent may use. Never raises."""
    from sqlalchemy import select

    from src.models.agent_tools import ProjectDataFile

    out = ""
    try:
        if slug in WEB_SEARCH_AGENTS:
            q = _query_from(answers, getattr(project, "client_name", ""))
            out += web_search.context_block(await web_search.search(q + " السعودية"))
        if slug in DATA_FILE_AGENTS:
            rows = (await session.execute(select(ProjectDataFile).where(ProjectDataFile.project_id == project.id)
                                          .order_by(ProjectDataFile.created_at.desc()).limit(5))).scalars().all()
            out += data_files.context_block([{"filename": r.filename, "summary": r.summary} for r in rows])
        if slug in STORE_AGENTS:
            out += store_connectors.context_block(await store_connectors.snapshots())
        if slug in KNOWLEDGE_AGENTS:
            q = _query_from(answers, "")
            hits = await knowledge_base.search(session, q, project_id=project.id, k=4) if q else []
            if not hits:
                docs = await knowledge_base.list_docs(session, project.id)
                hits = [{"title": d.title, "text": d.content[:1500]} for d in docs[:2]]
            out += knowledge_base.context_block(hits)
    except Exception:
        return out
    return out
