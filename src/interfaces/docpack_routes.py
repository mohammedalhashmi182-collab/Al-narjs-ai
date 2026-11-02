"""DocPack HTTP API.

POST /api/docpack          portal session or owner (same gate as the client portal)
POST /api/docpack/demo     public, rate-limited sample for the sales demo
GET  /api/docpack/files/{token}/{filename}
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from src.services.agent_tools import docpack_tool
from src.services.docgen import DocGenError
from src.services.docgen.analyze import MAX_UPLOAD_BYTES
from src.services.docgen.sample import load_sample_bytes
from src.services.docgen.store import PACKS
from src.utils.rate_limit import rate_limit_docpack_api, rate_limit_docpack_demo

router = APIRouter()


def _provider(request: Request):
    return docpack_tool.usable_provider(getattr(request.app.state, "model_provider", None))


async def _require_client(request: Request) -> dict:
    """Owner cookie, or a portal session for an active subscription."""
    from uuid import UUID

    from src.core.owner_auth import check_owner
    from src.core.portal_auth import session_claims, session_valid_for
    from src.models import ClientProject

    if check_owner(request):
        return {"role": "owner", "email": "", "client_name": "", "project_id": None}
    claims = session_claims(request)
    project_id = (claims or {}).get("p")
    if not project_id:
        raise HTTPException(401, "Portal login required")
    factory = request.app.state.session_factory
    async with factory() as session:
        try:
            project = await session.get(ClientProject, UUID(str(project_id)))
        except ValueError:
            project = None
        if not session_valid_for(claims, project):
            raise HTTPException(401, "Portal login required")
        if project.status != "active":
            raise HTTPException(402, "Subscription not active — activate your plan first")
        return {
            "role": "client",
            "email": project.email or "",
            "client_name": project.client_name or "",
            "project_id": str(project.id),
        }


async def _read_upload(upload: UploadFile | None) -> tuple[bytes | None, str | None]:
    if upload is None or not upload.filename:
        return None, None
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "الملف أكبر من 10 ميجابايت")
    return data, upload.filename


def _payload(pack, *, lang: str, emailed: bool) -> dict:
    published = docpack_tool.publish(pack)
    published["emailed"] = emailed
    for item in published["files"]:
        item["label"] = item["label_ar"] if lang != "en" else item["label_en"]
    return published


@router.post("/api/docpack", dependencies=[Depends(rate_limit_docpack_api)])
async def create_docpack(
    request: Request,
    file: UploadFile | None = File(None),
    brief: str = Form(""),
    agent_key: str = Form("data_analyst"),
    formats: str = Form(""),
):
    client = await _require_client(request)
    data, filename = await _read_upload(file)
    try:
        pack = await docpack_tool.build(
            slug=(agent_key or "").strip(),
            brief=brief,
            file_bytes=data,
            filename=filename,
            formats=formats,
            model_provider=_provider(request),
            client_name=client["client_name"],
        )
    except DocGenError as exc:
        raise HTTPException(400, str(exc)) from exc
    emailed = False
    if client["email"]:
        try:
            emailed = await docpack_tool.email_pack(client["email"], pack)
        except Exception:
            emailed = False
    return _payload(pack, lang="ar", emailed=emailed)


@router.post("/api/docpack/demo", dependencies=[Depends(rate_limit_docpack_demo)])
async def demo_docpack(
    request: Request,
    file: UploadFile | None = File(None),
    brief: str = Form(""),
    sample: str = Form(""),
    lang: str = Form("ar"),
):
    data, filename = await _read_upload(file)
    use_sample = str(sample).strip().lower() in {"1", "true", "yes", "on"}
    bundled = False
    if data is None and use_sample:
        data = load_sample_bytes()
        filename = "sales.xlsx"
        bundled = True
    text = (brief or "").strip()
    if data is not None and not text:
        text = "عيّنة توضيحية. الأرقام في الملف فقط، والعرض للتجربة."
    try:
        pack = await docpack_tool.build(
            slug="data_analyst",
            brief=text,
            file_bytes=data,
            filename=filename,
            formats=["pdf", "xlsx", "pptx"],
            model_provider=_provider(request),
            client_name="عيّنة توضيحية" if bundled else "",
            title_ar="تقرير العيّنة التوضيحية" if bundled else None,
            title_en="Illustrative sample report" if bundled else None,
        )
    except DocGenError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _payload(pack, lang="en" if lang == "en" else "ar", emailed=False)


@router.get("/api/docpack/files/{token}/{filename}")
async def download_docpack(token: str, filename: str):
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(404, "Not found")
    item = PACKS.get(token, filename)
    if item is None:
        raise HTTPException(404, "انتهت صلاحية الرابط أو الملف غير موجود")
    return Response(
        content=item.content,
        media_type=item.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{item.filename}"',
            "Cache-Control": "no-store",
        },
    )
