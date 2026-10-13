"""Knowledge base for customer service: FAQ text or PDF, chunked, retrieved by
token overlap (reusing the CEO advisor's Arabic-aware tokenizer). No embeddings,
no network. Owner docs (project_id NULL) feed the smart replies; project docs
feed that client's customer_service agent."""

from __future__ import annotations

import io
import os
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent_tools import KnowledgeDoc
from src.services import ceo_advisor

MAX_UPLOAD_BYTES = int(os.getenv("KB_UPLOAD_MAX_BYTES", str(3 * 1024 * 1024)))
MAX_CHARS = 200_000
CHUNK_CHARS = 700
MIN_SCORE = 2
STOPWORDS = frozenset("في من على الى إلى عن هل ما ماذا كيف كم و او أو مع هذا هذه the a an is are of to in for and or what how do does".split())


class KBError(ValueError):
    pass


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages[:200])
    except Exception as exc:
        raise KBError("تعذّر قراءة ملف PDF") from exc


def text_from_upload(filename: str, data: bytes) -> tuple[str, str]:
    if len(data) > MAX_UPLOAD_BYTES:
        raise KBError(f"الملف أكبر من الحد المسموح ({MAX_UPLOAD_BYTES // (1024 * 1024)} ميجابايت)")
    ext = (filename or "").rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        return pdf_text(data), "pdf"
    if ext in ("txt", "md", "csv"):
        return data.decode("utf-8-sig", errors="replace"), "text"
    raise KBError("نوع الملف غير مدعوم — TXT أو PDF")


async def add_doc(session: AsyncSession, title: str, content: str, *, project_id: UUID | None = None,
                  source: str = "text") -> KnowledgeDoc:
    content = (content or "").strip()[:MAX_CHARS]
    if len(content) < 10:
        raise KBError("المحتوى قصير جدًا")
    doc = KnowledgeDoc(project_id=project_id, title=(title or "FAQ").strip()[:255], content=content, source=source)
    session.add(doc)
    await session.commit()
    return doc


async def list_docs(session: AsyncSession, project_id: UUID | None = None) -> list[KnowledgeDoc]:
    cond = KnowledgeDoc.project_id.is_(None) if project_id is None else KnowledgeDoc.project_id == project_id
    return list((await session.execute(select(KnowledgeDoc).where(cond).order_by(KnowledgeDoc.created_at))).scalars())


async def delete_doc(session: AsyncSession, doc_id: UUID, project_id: UUID | None = None) -> bool:
    doc = await session.get(KnowledgeDoc, doc_id)
    if not doc or doc.project_id != project_id:
        return False
    await session.delete(doc)
    await session.commit()
    return True


def chunks(text: str) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out, cur = [], ""
    for p in paras:
        if cur and len(cur) + len(p) > CHUNK_CHARS:
            out.append(cur)
            cur = ""
        cur = f"{cur}\n{p}".strip()
        while len(cur) > CHUNK_CHARS * 2:
            out.append(cur[:CHUNK_CHARS])
            cur = cur[CHUNK_CHARS:]
    if cur:
        out.append(cur)
    return out


def _terms(text: str) -> set[str]:
    terms = set()
    for t in ceo_advisor.tokenize(text):
        if t in STOPWORDS or len(t) < 2:
            continue
        v = min(ceo_advisor._variants(t), key=len)
        terms.add(v)
    return terms


def search_texts(docs: list[tuple[str, str]], query: str, k: int = 3) -> list[dict]:
    q = _terms(query)
    if not q:
        return []
    scored = []
    for title, content in docs:
        for ch in chunks(content):
            score = len(q & _terms(ch))
            if score >= min(MIN_SCORE, len(q)):
                scored.append({"title": title, "text": ch, "score": score})
    scored.sort(key=lambda x: -x["score"])
    return scored[:k]


async def search(session: AsyncSession, query: str, *, project_id: UUID | None = None, k: int = 3) -> list[dict]:
    docs = await list_docs(session, project_id)
    return search_texts([(d.title, d.content) for d in docs], query, k)


def context_block(hits: list[dict]) -> str:
    if not hits:
        return ""
    body = "\n".join(f"• ({h['title']}) {h['text']}" for h in hits)
    return ("\n\n[قاعدة المعرفة — أجب منها فقط، وإن لم تجد الجواب قل إنك ستتحقق]:\n" + body)
