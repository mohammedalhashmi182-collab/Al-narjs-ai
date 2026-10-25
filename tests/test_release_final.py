"""Release-final guards: one linear alembic head, and a boot with Moyasar
pending (no keys / sandbox keys) that never crashes and never offers a card."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def test_alembic_has_one_linear_head() -> None:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == ["0017"]
    assert script.get_revision("0017").down_revision == "0016"
    revs = [r.revision for r in script.walk_revisions()]
    assert len(revs) == len(set(revs))
    assert script.get_revision("0016").down_revision == "0015"
    assert script.get_revision("0015").down_revision == "0014"


@pytest.mark.parametrize("secret,pub", [("", ""), ("sk_test_x", "pk_test_x")])
def test_boot_with_moyasar_pending_is_clean(monkeypatch, secret, pub) -> None:
    from src.config import get_settings
    from src.main import app

    s = get_settings()
    monkeypatch.setattr(s, "moyasar_api_secret", secret, raising=False)
    monkeypatch.setattr(s, "moyasar_publishable_key", pub, raising=False)
    with TestClient(app) as c:
        r = c.get("/api/payments/capabilities")
        assert r.status_code == 200
        body = r.json()
        assert body["card"] is False
        assert body["moyasar_status"] == "pending"
        assert body["moyasar_on_hold"] is True
        for path in ("/", "/portal"):
            assert c.get(path).status_code < 500
