"""Owner tool: put legacy active subscribers on the renewal cycle and staff add-ons.

    python scripts/backfill_subscriptions.py          # dry run (default)
    python scripts/backfill_subscriptions.py --apply  # write

Uses DATABASE_URL from the environment. Sends nothing.
"""
import asyncio
import json
import sys


async def main(apply: bool) -> None:
    from src.db.session import async_session_factory
    from src.services.renewals import backfill_legacy_subscriptions

    async with async_session_factory() as session:
        result = await backfill_legacy_subscriptions(session, dry_run=not apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv))
