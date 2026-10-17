"""Recreate ``embedding_vec`` as an unconstrained ``vector``. Manual admin path.

Indexing refuses to ``DROP COLUMN`` on a live request. Run this when the column
was created as ``vector(N)`` and the embedding width changed.

    python scripts/rebuild_embedding_vec.py

Postgres only. After it commits, the background indexer fills the column again.
"""

from __future__ import annotations

import asyncio
import sys


async def main() -> int:
    from src.db.session import async_session_factory
    from src.services.rag.store import rebuild_embedding_vec_column

    try:
        async with async_session_factory() as session:
            await rebuild_embedding_vec_column(session)
            await session.commit()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("embedding_vec is an unconstrained vector. Background indexing fills it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
