import os
import tempfile

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("OWNER_PASSWORD", "test-owner-password-not-for-production")
os.environ.setdefault("ENVIRONMENT", "test")

# One SQLite file per pytest process. The old shared ./test_ai_agent_system.db
# leaked rows and locks across runs and xdist workers.
_db_now = os.environ.get("DATABASE_URL", "")
_shared_sqlite = _db_now.endswith("test_ai_agent_system.db") or _db_now.endswith("ai_agent_system.db")
if not _db_now or _shared_sqlite:
    _worker = os.environ.get("PYTEST_XDIST_WORKER", "master")
    _db_dir = tempfile.mkdtemp(prefix=f"narjis-pytest-{_worker}-{os.getpid()}-")
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + os.path.join(_db_dir, "test.db")


import pytest as _pytest


@_pytest.fixture
def founding_full(monkeypatch):
    """All founding seats taken: checkout prices at the regular rate.

    Checkout auto-applies the founding offer while seats remain; tests that
    assert regular pricing through the public API use this fixture.
    """
    from src.services import catalog

    monkeypatch.setitem(catalog.FOUNDING_OFFER, "seats", 0)


@_pytest.fixture(autouse=True)
def _reset_payment_idempotency_cache():
    """The /api/payments replay cache is process-global; never let one test's
    response be replayed into another test (that caused the flaky PayPal tests)."""
    from src import main

    main._payment_replays.clear()
    main._payment_locks.clear()
    yield
    main._payment_replays.clear()
    main._payment_locks.clear()


@_pytest.fixture(autouse=True)
def _rag_offline(monkeypatch):
    """RAG never calls a real embedding/LLM provider in tests: hash embeddings,
    and no LLM unless a test installs its own mock on ``generate._llm_complete``."""
    from src.services.rag import embeddings, generate

    monkeypatch.setenv("RAG_EMBED_PROVIDER", "hash")
    embeddings.set_embedder(None)

    async def _no_llm(system, prompt):
        return None

    monkeypatch.setattr(generate, "_llm_complete", _no_llm)
    yield
    embeddings.set_embedder(None)


@_pytest.fixture
def vat15(monkeypatch):
    """Opt a test into the legacy VAT-registered behaviour (VAT_RATE=0.15).
    Production default is 0 (operator not VAT-registered)."""
    monkeypatch.setenv("VAT_RATE", "0.15")
    yield
