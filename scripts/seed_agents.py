#!/usr/bin/env python
"""Seed script to load base agents into database."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.db.session import init_db, get_session_factory
from src.core.agent_registry import AgentRegistry


async def main():
    settings = get_settings()
    
    print("Initializing database...")
    await init_db()
    
    session_factory = await get_session_factory()
    registry = AgentRegistry(session_factory)
    
    print("Syncing base agents...")
    agents = await registry.sync_base_agents()
    
    print(f"\nSuccessfully synced {len(agents)} agents:")
    for agent in agents:
        print(f"  - {agent.slug}: {agent.name} ({agent.category.value})")
    
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())