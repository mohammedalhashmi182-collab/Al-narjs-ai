"""Ingest a local mailbox snapshot into the funnel. Does not contact Gmail.

Refuses when ENVIRONMENT=production. Refuses unless ``--fixture`` points at a
local JSON file. Never sends mail.

The JSON file is a list of objects: message_id, from, to, in_reply_to, text, occurred_at.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from src.services.gmail_reconcile import MailSnapshot, refuse_reason


def _snapshot(row: dict) -> MailSnapshot:
    occurred = row.get("occurred_at")
    when = datetime.fromisoformat(occurred) if occurred else None
    recipients = row.get("to") or []
    if isinstance(recipients, str):
        recipients = [recipients]
    return MailSnapshot(
        message_id=str(row.get("message_id") or ""),
        from_addr=str(row.get("from") or ""),
        to_addrs=tuple(str(item) for item in recipients),
        in_reply_to=row.get("in_reply_to"),
        occurred_at=when,
        text=str(row.get("text") or ""),
    )


async def _run(path: Path) -> dict:
    from src.db.session import async_session_factory

    rows = json.loads(path.read_text(encoding="utf-8"))
    messages = [_snapshot(row) for row in rows]
    async with async_session_factory() as session:
        from src.services.gmail_reconcile import ingest_snapshot

        report = await ingest_snapshot(session, messages)
        await session.commit()
    return report


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    reason = refuse_reason(os.environ.get("ENVIRONMENT"), argv)
    if reason:
        print(reason)
        return 2
    fixture = argv[argv.index("--fixture") + 1]
    report = asyncio.run(_run(Path(fixture)))
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
