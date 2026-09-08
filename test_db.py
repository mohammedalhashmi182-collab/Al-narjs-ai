from src.db.session import init_db, get_session_factory, engine, close_db
from src.models import Base
import asyncio

async def test():
    print("Testing DB init...")
    try:
        await init_db()
        print("OK init_db succeeded")
        
        # Verify table was created
        async with engine.begin() as conn:
            tables = await conn.run_sync(lambda sync_conn: Base.metadata.tables.keys())
            print(f"OK Tables created: {list(tables)}")
    except Exception as e:
        print(f"FAIL init_db failed: {e}")
        import traceback
        traceback.print_exc()
    
    await close_db()

asyncio.run(test())