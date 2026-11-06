"""Legal pages name the freelance-document holder. Other static files do not hardcode it."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app

ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"زهراني|غرم\s*الله|عبدالله الزهراني|zahrani|ghurm", re.IGNORECASE)
PUBLIC_DIRS = [ROOT / "src" / "web" / "templates", ROOT / "src" / "web" / "static", ROOT / "static"]
HOLDER_AR = "أحمد عبدالله غرم الله الزهراني"
HOLDER_EN = "Ahmed Abdullah Ghurmullah Alzahrani"
DOC = "FL-272182297"


def test_templates_and_static_files_do_not_hardcode_the_holder_name():
    hits = []
    for d in PUBLIC_DIRS:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if p.is_file() and p.suffix in {".html", ".txt", ".xml", ".js", ".json", ".md", ".css", ".svg", ".webmanifest"}:
                if NAME_RE.search(p.read_text(encoding="utf-8", errors="ignore")):
                    hits.append(str(p.relative_to(ROOT)))
    assert hits == []


def test_freelance_defaults_live_in_settings_and_email_uses_the_helper():
    src = (ROOT / "src" / "config" / "settings.py").read_text(encoding="utf-8")
    assert HOLDER_AR in src and HOLDER_EN in src and DOC in src
    email = (ROOT / "src" / "services" / "email_service.py").read_text(encoding="utf-8")
    assert "freelance_holder_name" in email
    assert not NAME_RE.search(email)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("path", [
    "/ar/home", "/en/home", "/ar/about", "/en/about", "/ar/contact", "/en/contact",
    "/ar/terms", "/en/terms", "/ar/privacy", "/en/privacy", "/ar/refund-policy", "/en/refund-policy",
    "/ar/dpa", "/en/dpa", "/ar/pricing", "/en/pricing", "/portal",
])
def test_rendered_public_pages_show_the_freelance_identity(client, path):
    r = client.get(path, follow_redirects=True)
    if r.status_code == 404:
        pytest.skip(f"{path} not served")
    assert r.status_code == 200
    assert "سجل تجاري" not in r.text
    assert DOC in r.text
    english = path.startswith("/en/") or 'lang="en"' in r.text[:800]
    if english:
        assert HOLDER_EN in r.text
        assert "Not VAT-registered" in r.text
    else:
        assert HOLDER_AR in r.text
        assert "غير مسجل في ضريبة القيمة المضافة" in r.text
        assert "وثيقة عمل حر رقم:" in r.text


def test_blank_freelance_settings_fall_back_to_placeholders(monkeypatch):
    from src.config.settings import get_settings
    from src.services import legal_identity

    settings = get_settings()
    monkeypatch.delenv("FREELANCE_DOC_NUMBER", raising=False)
    monkeypatch.delenv("FREELANCE_HOLDER_NAME", raising=False)
    monkeypatch.delenv("FREELANCE_HOLDER_NAME_EN", raising=False)
    monkeypatch.delenv("SELLER_CR_NUMBER", raising=False)
    assert legal_identity.freelance_doc_number() == DOC
    assert legal_identity.freelance_holder_name() == HOLDER_AR
    assert legal_identity.freelance_holder_name_en() == HOLDER_EN
    monkeypatch.setattr(settings, "freelance_doc_number", "")
    monkeypatch.setattr(settings, "seller_cr_number", "")
    monkeypatch.setattr(settings, "freelance_holder_name", "")
    monkeypatch.setattr(settings, "freelance_holder_name_en", "")
    assert legal_identity.freelance_doc_number() == "{{FREELANCE_DOC_NUMBER}}"
    assert legal_identity.freelance_holder_name() == "{{FREELANCE_HOLDER_NAME}}"
    assert legal_identity.freelance_holder_name_en() == "{{FREELANCE_HOLDER_NAME_EN}}"
