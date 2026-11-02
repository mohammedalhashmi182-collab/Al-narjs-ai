"""Release-final guards: one linear alembic head, and a boot that never offers a card."""
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
    assert script.get_heads() == ["0018"]
    assert script.get_revision("0018").down_revision == "0017"
    assert script.get_revision("0017").down_revision == "0016"
    revs = [r.revision for r in script.walk_revisions()]
    assert len(revs) == len(set(revs))
    assert script.get_revision("0016").down_revision == "0015"
    assert script.get_revision("0015").down_revision == "0014"


def test_boot_offers_no_card_checkout() -> None:
    from src.main import app

    with TestClient(app) as c:
        r = c.get("/api/payments/capabilities")
        assert r.status_code == 200
        body = r.json()
        assert body["card"] is False
        assert set(body["methods"]) == {"paypal", "invoice"}
        assert "moyasar" not in r.text.lower()
        for path in ("/", "/portal"):
            assert c.get(path).status_code < 500
