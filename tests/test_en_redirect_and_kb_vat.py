from pathlib import Path

import pytest
from fastapi.testclient import TestClient

KB = Path(__file__).resolve().parents[1] / "data" / "kb" / "narjs_services.md"


def test_kb_does_not_claim_vat():
    text = KB.read_text(encoding="utf-8")
    assert "15%" not in text
    assert "قبل ضريبة" not in text and "قبل الضريبة" not in text
    assert "تُضاف ضريبة" not in text
    assert "يحدده محمد" not in text


@pytest.fixture(scope="module")
def client():
    from src.main import app
    return TestClient(app)


@pytest.mark.parametrize("path", ["/en", "/en/", "/ar", "/ar/", "/"])
def test_locale_roots_land_on_200(client, path):
    r = client.get(path, follow_redirects=True)
    assert r.status_code == 200, (path, r.status_code, r.url)
    assert len(r.history) <= 3
    assert "/en/ar" not in str(r.url)
