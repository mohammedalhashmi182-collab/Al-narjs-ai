"""Render a portal fixture without starting an external server or using real data.

Run from repo root: python tests/browser/render_portal.py /tmp/portal-ux.html
Then: NARJIS_PORTAL_HTML=/tmp/portal-ux.html node tests/browser/portal-ux.cjs
Requires Node Playwright and a local Chromium; set CHROMIUM_PATH if needed.
"""
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault('SECRET_KEY', 'test-secret-key-not-for-production')
os.environ.setdefault('OWNER_PASSWORD', 'test-password-not-for-production')
os.environ.setdefault('ENVIRONMENT', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///' + str(Path(tempfile.mkdtemp()) / 'local.db'))

from fastapi.testclient import TestClient  # noqa: E402
from src.main import app  # noqa: E402

response = TestClient(app).get('/ar/portal?billing=annual')
response.raise_for_status()
Path(sys.argv[1]).write_text(response.text, encoding='utf-8')
