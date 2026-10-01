"""Meta Pixel contract for the public pages.

The Pixel partial already existed but was gated on ``settings.meta_pixel_id``,
which was never set, so both public pages shipped *no* tracking at all. These
tests pin the contract so a missing ID or a moved include fails CI instead of
silently disabling attribution:

- the standard snippet, ``fbq('init', id)`` and ``fbq('track', 'PageView')`` are
  inside ``<head>`` (not deferred into ``<body>``) on /home and /early-access
- the snippet is loaded exactly once per page (a second include would double-fire
  init and inflate every PageView)
- the ``<noscript>`` image fallback matches the configured ID
- a configured ID never leaks a token-like value into the HTML
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from src.main import app

PIXEL_ID = "1097204086820069"

PUBLIC_PAGES = ("/home", "/early-access", "/ar/home", "/ar/early-access")

INIT_RE = re.compile(r"fbq\(\s*'init'\s*,\s*'([0-9]{10,20})'\s*\)")
TRACK_RE = re.compile(r"fbq\(\s*'track'\s*,\s*'PageView'\s*\)")
FBEVENTS_RE = re.compile(r"connect\.facebook\.net/[a-zA-Z_]+/fbevents\.js")
NOSCRIPT_RE = re.compile(r"facebook\.com/tr\?id=([0-9]{10,20})&amp;ev=PageView")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def pixel_configured():
    from src.config.settings import settings

    if not settings.meta_pixel_id:
        pytest.skip("META_PIXEL_ID is not configured in this environment")
    return settings.meta_pixel_id


def _head_of(html: str) -> str:
    """The <head> region, or the whole document when the marker is missing."""
    start = html.lower().find("<head>")
    end = html.lower().find("</head>")
    if start == -1 or end == -1:
        return html
    return html[start:end]


class TestPixelInHead:
    @pytest.mark.parametrize("path", PUBLIC_PAGES)
    def test_init_and_pageview_are_inside_head(self, client: TestClient, path: str, pixel_configured):
        r = client.get(path)
        assert r.status_code == 200, path
        head = _head_of(r.text)
        init = INIT_RE.search(head)
        assert init, f"fbq('init') is not inside <head> on {path}"
        assert init.group(1) == pixel_configured, path
        assert TRACK_RE.search(head), f"fbq('track','PageView') is not inside <head> on {path}"
        assert FBEVENTS_RE.search(head), f"fbevents.js is not inside <head> on {path}"

    @pytest.mark.parametrize("path", PUBLIC_PAGES)
    def test_pixel_is_loaded_exactly_once(self, client: TestClient, path: str, pixel_configured):
        html = client.get(path).text
        assert len(INIT_RE.findall(html)) == 1, f"duplicate fbq('init') on {path} double-counts PageView"
        assert len(FBEVENTS_RE.findall(html)) == 1, f"fbevents.js included twice on {path}"
        assert len(TRACK_RE.findall(html)) == 1, f"PageView tracked twice on {path}"

    @pytest.mark.parametrize("path", PUBLIC_PAGES)
    def test_noscript_fallback_matches_id(self, client: TestClient, path: str, pixel_configured):
        html = client.get(path).text
        found = NOSCRIPT_RE.search(html)
        assert found, f"missing <noscript> PageView fallback on {path}"
        assert found.group(1) == pixel_configured, path


class TestPixelHardening:
    def test_no_token_like_value_is_rendered(self, client: TestClient, pixel_configured):
        """A Pixel ID is a public client-side identifier; an access token is not."""
        html = client.get("/home").text
        for marker in ("EAA", "access_token", "client_secret", "app_secret"):
            assert marker not in html, f"{marker} must never appear in a public page"

    def test_pixel_snippet_is_async_and_non_blocking(self, pixel_configured):
        """The loader must stay async so a blocked CDN cannot delay first paint."""
        from pathlib import Path

        from src.main import templates as _t  # noqa: F401  (ensure jinja env import path)

        partial = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "web"
            / "templates"
            / "partials"
            / "_analytics.html"
        ).read_text(encoding="utf-8")
        assert "t.async=!0" in partial
        assert "n.version='2.0'" in partial

    def test_partial_is_reachable_from_both_public_templates(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "src" / "web" / "templates"
        for name in ("landing.html", "early_access.html"):
            text = (root / name).read_text(encoding="utf-8")
            assert 'include "partials/_analytics.html"' in text, name

    def test_analytics_partial_is_inside_head_of_both_templates(self):
        """Static guard: the include must sit before </head>, not in the body."""
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "src" / "web" / "templates"
        marker = 'include "partials/_analytics.html"'
        for name in ("landing.html", "early_access.html"):
            text = (root / name).read_text(encoding="utf-8")
            include_at = text.index(marker)
            head_end = text.lower().index("</head>")
            assert include_at < head_end, f"{name} loads the pixel after </head>"

    def test_unconfigured_pixel_renders_nothing(self):
        """Without an ID the partial must not ship a broken stub."""
        from pathlib import Path

        partial = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "web"
            / "templates"
            / "partials"
            / "_analytics.html"
        ).read_text(encoding="utf-8")
        assert "{% if settings.meta_pixel_id %}" in partial