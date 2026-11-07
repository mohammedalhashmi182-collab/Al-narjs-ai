"""Browser checks for the home intro (plays on every visit). Run with RUN_BROWSER_TESTS=1."""
import os
from urllib.parse import urlsplit

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get('RUN_BROWSER_TESTS') != '1', reason='set RUN_BROWSER_TESTS=1 for Chromium checks'
)


@pytest.fixture(scope='module')
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get('BROWSER_EXECUTABLE_PATH'))
        yield browser
        browser.close()


@pytest.fixture(scope='module')
def client():
    from fastapi.testclient import TestClient
    from src.main import app
    with TestClient(app) as c:
        yield c


def _ctx(browser, client, **kw):
    ctx = browser.new_context(**kw)
    def serve(route):
        url = urlsplit(route.request.url)
        r = client.request(route.request.method, url.path + ('?' + url.query if url.query else ''),
                           content=route.request.post_data_buffer)
        route.fulfill(status=r.status_code, body=r.content,
                      headers={'content-type': r.headers.get('content-type', 'text/plain')})
    ctx.route('**/*', lambda route: route.abort())
    ctx.route('http://testserver/**', serve)
    return ctx


def _errors(page):
    errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.on('console', lambda m: m.type == 'error' and 'net::ERR_FAILED' not in m.text and errs.append(m.text))
    return errs


@pytest.mark.parametrize('lang,width', [('ar', 320), ('ar', 390), ('en', 768), ('en', 1440)])
def test_compact_in_page_wordmark_never_blocks_hero(browser, client, lang, width):
    ctx = _ctx(browser, client, viewport={'width': width, 'height': 844})
    page = ctx.new_page()
    errs = _errors(page)
    for _ in range(2):
        page.goto(f'http://testserver/{lang}/home')
        assert page.locator('#njIntro').count() == 0
        assert not page.evaluate("document.documentElement.classList.contains('nj-intro-on')")
        logo = page.locator('.nj-wordmark')
        assert logo.is_visible()
        assert logo.inner_text().strip() == 'النرجس'
        bounds = logo.bounding_box()
        assert bounds is not None and bounds['height'] < 72, bounds
        assert bounds['width'] < width - 20
        page.locator('#heroCeo').click(trial=True, timeout=5000)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    assert not errs
    ctx.close()


@pytest.mark.parametrize('lang', ['ar', 'en'])
def test_wordmark_respects_reduced_motion(browser, client, lang):
    ctx = _ctx(browser, client, viewport={'width': 390, 'height': 844}, reduced_motion='reduce')
    page = ctx.new_page()
    page.goto(f'http://testserver/{lang}/home')
    assert page.locator('.nj-wordmark').is_visible()
    assert page.locator('.nj-wordmark').evaluate(
        "(el) => getComputedStyle(el).animationName"
    ) == 'none'
    assert page.locator('#njIntro').count() == 0
    page.locator('#heroCeo').click(trial=True, timeout=5000)
    ctx.close()
