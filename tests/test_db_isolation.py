"""The suite must not share one SQLite file across processes."""
import os


def test_database_url_is_a_private_sqlite_file():
    url = os.environ["DATABASE_URL"]
    worker = os.environ.get("PYTEST_XDIST_WORKER", "master")
    assert url.startswith("sqlite+aiosqlite:///")
    assert "test_ai_agent_system.db" not in url
    assert worker in url
    assert str(os.getpid()) in url
