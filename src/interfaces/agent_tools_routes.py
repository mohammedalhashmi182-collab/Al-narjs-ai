"""Agent tools API.

Portal (a portal session for the project is required, see src/core/portal_auth.py;
the subscription must be active):
  POST   /api/portal/projects/{pid}/files           multipart CSV/XLSX -> data_analyst
  GET    /api/portal/projects/{pid}/files
  POST   /api/portal/projects/{pid}/knowledge       multipart TXT/PDF or form text -> customer_service
  GET    /api/portal/projects/{pid}/knowledge
  DELETE /api/portal/projects/{pid}/knowledge/{doc_id}
Owner (cookie auth):
  GET    /api/owner/tools/status                    which tools are configured (never secret values)
  GET/POST/DELETE /api/owner/knowledge[/{doc_id}]   owner FAQ used by smart replies
  GET    /api/owner/stores/{platform}/snapshot      read-only products/orders
  GET    /api/owner/stores/{platform}/connect       OAuth authorize URL (owner installs the app)
Nothing here sends a message or writes to a store.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select

from src.core.owner_auth import require_owner
from src.models import ClientProject
from src.models.agent_tools import ProjectDataFile
from src.services import agent_tools
from src.services.agent_tools import data_files, knowledge_base, store_connectors

router = APIRouter()


def _factory(request: Request):
    return request.app.state.session_factory


def _uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise HTTPException(404, "Not found")


async def _active_project(session, pid: str, request: Request) -> ClientProject:
    from src.core.portal_auth import require_portal_project

    project = await require_portal_project(session, request, pid)
    if project.status != "active":
        raise HTTPException(402, "Subscription not active — activate your plan first")
    return project


async def _read_limited(upload: UploadFile, limit: int) -> bytes:
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"الملف أكبر من الحد المسموح ({limit // (1024 * 1024)} ميجابايت)")
    return data


def _doc(d) -> dict:
    return {"id": str(d.id), "title": d.title, "source": d.source, "chars": len(d.content or ""),
            "created_at": d.created_at.isoformat() if d.created_at else None}


# ---------------------------------------------------------------- portal: data files
@router.post("/api/portal/projects/{pid}/files")
async def upload_data_file(pid: str, request: Request, file: UploadFile = File(...)):
    data = await _read_limited(file, data_files.MAX_UPLOAD_BYTES)
    try:
        summary = data_files.parse(file.filename or "", data)
    except data_files.UploadError as exc:
        raise HTTPException(400, str(exc))
    async with _factory(request)() as session:
        project = await _active_project(session, pid, request)
        row = ProjectDataFile(project_id=project.id, filename=(file.filename or "data")[:255],
                              kind=summary["kind"], size_bytes=len(data), summary=summary)
        session.add(row)
        await session.commit()
        return {"id": str(row.id), "filename": row.filename, "rows": summary["rows"],
                "columns": [c["name"] for c in summary["columns"]]}


@router.get("/api/portal/projects/{pid}/files")
async def list_data_files(pid: str, request: Request):
    async with _factory(request)() as session:
        project = await _active_project(session, pid, request)
        rows = (await session.execute(select(ProjectDataFile).where(ProjectDataFile.project_id == project.id)
                                      .order_by(ProjectDataFile.created_at))).scalars().all()
        return {"files": [{"id": str(r.id), "filename": r.filename, "kind": r.kind, "size_bytes": r.size_bytes,
                           "rows": (r.summary or {}).get("rows")} for r in rows]}


# ---------------------------------------------------------------- knowledge base
async def _kb_payload(file: UploadFile | None, text: str | None, title: str | None) -> tuple[str, str, str]:
    if file is not None and file.filename:
        data = await _read_limited(file, knowledge_base.MAX_UPLOAD_BYTES)
        try:
            content, source = knowledge_base.text_from_upload(file.filename, data)
        except knowledge_base.KBError as exc:
            raise HTTPException(400, str(exc))
        return title or file.filename, content, source
    if text:
        return title or "FAQ", text, "text"
    raise HTTPException(400, "أرسل ملفًا (TXT/PDF) أو نصًا")


@router.post("/api/portal/projects/{pid}/knowledge")
async def portal_add_knowledge(pid: str, request: Request, file: UploadFile | None = File(None),
                               text: str | None = Form(None), title: str | None = Form(None)):
    t, content, source = await _kb_payload(file, text, title)
    async with _factory(request)() as session:
        project = await _active_project(session, pid, request)
        try:
            doc = await knowledge_base.add_doc(session, t, content, project_id=project.id, source=source)
        except knowledge_base.KBError as exc:
            raise HTTPException(400, str(exc))
        return _doc(doc)


@router.get("/api/portal/projects/{pid}/knowledge")
async def portal_list_knowledge(pid: str, request: Request):
    async with _factory(request)() as session:
        project = await _active_project(session, pid, request)
        return {"docs": [_doc(d) for d in await knowledge_base.list_docs(session, project.id)]}


@router.delete("/api/portal/projects/{pid}/knowledge/{doc_id}")
async def portal_delete_knowledge(pid: str, doc_id: str, request: Request):
    async with _factory(request)() as session:
        project = await _active_project(session, pid, request)
        if not await knowledge_base.delete_doc(session, _uuid(doc_id), project.id):
            raise HTTPException(404, "Not found")
        return {"deleted": True}


@router.get("/api/owner/knowledge", dependencies=[Depends(require_owner)])
async def owner_list_knowledge(request: Request):
    async with _factory(request)() as session:
        return {"docs": [_doc(d) for d in await knowledge_base.list_docs(session, None)]}


@router.post("/api/owner/knowledge", dependencies=[Depends(require_owner)])
async def owner_add_knowledge(request: Request, file: UploadFile | None = File(None),
                              text: str | None = Form(None), title: str | None = Form(None)):
    t, content, source = await _kb_payload(file, text, title)
    async with _factory(request)() as session:
        try:
            return _doc(await knowledge_base.add_doc(session, t, content, project_id=None, source=source))
        except knowledge_base.KBError as exc:
            raise HTTPException(400, str(exc))


@router.delete("/api/owner/knowledge/{doc_id}", dependencies=[Depends(require_owner)])
async def owner_delete_knowledge(doc_id: str, request: Request):
    async with _factory(request)() as session:
        if not await knowledge_base.delete_doc(session, _uuid(doc_id), None):
            raise HTTPException(404, "Not found")
        return {"deleted": True}


# ---------------------------------------------------------------- owner: status + stores
@router.get("/api/owner/tools/status", dependencies=[Depends(require_owner)])
async def tools_status():
    return agent_tools.status()


@router.get("/api/owner/stores/{platform}/snapshot", dependencies=[Depends(require_owner)])
async def store_snapshot(platform: str):
    try:
        return await store_connectors.get(platform).snapshot()
    except KeyError:
        raise HTTPException(404, "Unknown platform")


@router.get("/api/owner/stores/{platform}/connect", dependencies=[Depends(require_owner)])
async def store_connect(platform: str):
    try:
        conn = store_connectors.get(platform)
    except KeyError:
        raise HTTPException(404, "Unknown platform")
    url = conn.authorize_url(state="owner")
    if not url:
        p = platform.upper()
        return {"configured": False, "message": f"Set {p}_CLIENT_ID and {p}_REDIRECT_URI first"}
    return {"configured": True, "authorize_url": url}
