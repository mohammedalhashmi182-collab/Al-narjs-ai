import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("OWNER_PASSWORD", "test-owner-password-not-for-production")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_ai_agent_system.db")


import pytest as _pytest


@_pytest.fixture
def founding_full(monkeypatch):
    """All founding seats taken: checkout prices at the regular rate.

    Checkout auto-applies the founding offer while seats remain; tests that
    assert regular pricing through the public API use this fixture.
    """
    from src.services import catalog

    monkeypatch.setitem(catalog.FOUNDING_OFFER, "seats", 0)
