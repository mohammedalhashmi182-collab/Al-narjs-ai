"""Markdown knowledge base retrieved through the pgvector RAG store.

``src.services.rag.store`` is the only vector store: on Postgres with the
``vector`` extension similarity runs in pgvector; elsewhere the same store
uses in-process cosine. Qdrant is not used.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from sqlalchemy import select

COLLECTION_PREFIX = "kb:"
CHUNK_CHARS = 800

# Answers carrying these markers are unfinished: never sent to a customer.
BLOCK_MARKERS = ("[X]", "يحدده محمد")

DEFAULT_KB = Path(__file__).resolve().parents[2] / "data" / "kb" / "narjs_services.md"


def is_blocked(text: str) -> bool:
    return any(m in (text or "") for m in BLOCK_MARKERS)


def chunk_markdown(text: str, source: str) -> list[dict]:
    """One chunk per heading section (a Q&A stays whole); long sections split by paragraph."""
    sections = re.split(r"\n(?=#{1,4} )", text or "")
    out: list[dict] = []
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        title = sec.splitlines()[0].lstrip("# ").strip()
        if len(sec) <= CHUNK_CHARS:
            out.append({"text": sec, "title": title, "source": source})
            continue
        cur = ""
        for para in sec.split("\n\n"):
            if cur and len(cur) + len(para) > CHUNK_CHARS:
                out.append({"text": cur, "title": title, "source": source})
                cur = ""
            cur = f"{cur}\n\n{para}".strip()
        if cur:
            out.append({"text": cur, "title": title, "source": source})
    return out


def source_label(path: Path) -> str:
    """Repo-relative path when the file lives in the tree; otherwise the given path."""
    resolved = path.resolve()
    root = Path(__file__).resolve().parents[2]
    try:
        return str(resolved.relative_to(root))
    except ValueError:
        return str(resolved)


class KB:
    """Index markdown into ``KnowledgeDoc`` and retrieve via ``src.services.rag.store``."""

    def __init__(self, session):
        self.session = session

    async def ingest(self, path: str | Path) -> int:
        from src.models.agent_tools import KnowledgeDoc
        from src.services.rag import store

        p = Path(path)
        files = sorted(x for x in p.rglob("*.md") if x.is_file()) if p.is_dir() else [p]
        n = 0
        for f in files:
            label = source_label(f)
            title = f"{COLLECTION_PREFIX}{label}"[:255]
            chunks = chunk_markdown(f.read_text(encoding="utf-8"), label)
            old = (await self.session.execute(
                select(KnowledgeDoc).where(
                    KnowledgeDoc.project_id.is_(None),
                    KnowledgeDoc.title == title,
                )
            )).scalars().all()
            for doc in old:
                await store.delete_doc_chunks(self.session, doc.id)
                await self.session.delete(doc)
            await self.session.flush()
            for ch in chunks:
                doc = KnowledgeDoc(project_id=None, title=title, content=ch["text"], source="text")
                self.session.add(doc)
                await self.session.flush()
                await store.index_doc(self.session, doc)
                n += 1
        await self.session.commit()
        return n

    async def ensure_default(self) -> None:
        """Index ``data/kb/narjs_services.md`` when it is missing or its text changed."""
        from src.models.agent_tools import KnowledgeDoc

        path = DEFAULT_KB
        if not path.is_file():
            return
        label = source_label(path)
        title = f"{COLLECTION_PREFIX}{label}"[:255]
        chunks = chunk_markdown(path.read_text(encoding="utf-8"), label)
        existing = (await self.session.execute(
            select(KnowledgeDoc.content).where(
                KnowledgeDoc.project_id.is_(None),
                KnowledgeDoc.title == title,
            )
        )).scalars().all()
        digest = hashlib.sha256("\n".join(sorted(existing)).encode()).hexdigest()
        want = hashlib.sha256("\n".join(sorted(c["text"] for c in chunks)).encode()).hexdigest()
        if existing and digest == want and len(existing) == len(chunks):
            return
        await self.ingest(path)

    async def retrieve(self, q: str, k: int = 5) -> list[dict]:
        from src.services.rag import store

        hits = await store.retrieve(
            self.session, q, project_id=None, k=k, title_prefix=COLLECTION_PREFIX,
        )
        out = []
        for h in hits:
            title = h.get("title") or ""
            source = title[len(COLLECTION_PREFIX):] if title.startswith(COLLECTION_PREFIX) else title
            out.append({**h, "source": source})
        return out
