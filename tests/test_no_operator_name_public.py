"""The operator's personal name must not appear on any public page or template."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app

ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"زهراني|غرم\s*الله|عبدالله الزهراني|zahrani|ghurm", re.IGNORECASE)
PUBLIC_DIRS = [ROOT / "src" / "web" / "templates", ROOT / "src" / "web" / "static", ROOT / "static"]


def test_no_template_or_static_file_contains_operator_name():
    hits = []
    for d in PUBLIC_DIRS:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if p.is_file() and p.suffix in {".html", ".txt", ".xml", ".js", ".json", ".md", ".css", ".svg", ".webmanifest"}:
                if NAME_RE.search(p.read_text(encoding="utf-8", errors="ignore")):
                    hits.append(str(p.relative_to(ROOT)))
    assert hits == []


def test_invoice_seller_defaults_and_email_label_use_brand():
    src = (ROOT / "src" / "config" / "settings.py").read_text(encoding="utf-8")
    assert not NAME_RE.search(src)
    assert not NAME_RE.search((ROOT / "src" / "services" / "email_service.py").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("path", [
    "/ar/home", "/en/home", "/ar/about", "/en/about", "/ar/contact", "/en/contact",
    "/ar/terms", "/en/terms", "/ar/privacy", "/en/privacy", "/ar/refund-policy", "/en/refund-policy",
    "/ar/dpa", "/en/dpa", "/ar/pricing", "/en/pricing", "/portal", "/llms.txt", "/sitemap.xml", "/robots.txt",
])
def test_rendered_public_pages_have_no_operator_name(client, path):
    r = client.get(path)
    if r.status_code == 404:
        pytest.skip(f"{path} not served")
    assert not NAME_RE.search(r.text), path
    if path.endswith(("about", "terms", "privacy", "dpa")):
        assert "FL-272182297" in r.text, path
