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
        r = client.get(url.path + ('?' + url.query if url.query else ''))
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


@pytest.mark.parametrize('lang,width', [('ar', 390), ('en', 1440)])
def test_intro_plays_every_visit_and_auto_dismiss(browser, client, lang, width):
    ctx = _ctx(browser, client, viewport={'width': width, 'height': 844})
    page = ctx.new_page()
    errs = _errors(page)
    page.goto(f'http://testserver/{lang}/home')
    assert page.locator('#njIntro').is_visible()
    assert page.locator('.nj-intro-skip').is_visible()
    # gone (removed from DOM) within ~3.2s
    page.wait_for_selector('#njIntro', state='detached', timeout=3500)
    page.locator('#heroCeo').click(trial=True, timeout=1000)
    page.reload()
    assert page.locator('#njIntro').is_visible()
    page.wait_for_selector('#njIntro', state='detached', timeout=3500)
    page.locator('#heroCeo').click(trial=True, timeout=1000)
    assert errs == []
    ctx.close()


def test_intro_skip_button(browser, client):
    ctx = _ctx(browser, client, viewport={'width': 390, 'height': 844})
    page = ctx.new_page()
    page.goto('http://testserver/en/home')
    page.locator('.nj-intro-skip').click()
    page.wait_for_selector('#njIntro', state='detached', timeout=1000)
    page.locator('#heroCeo').click(trial=True, timeout=1000)
    ctx.close()


def test_intro_reduced_motion_never_shows(browser, client):
    ctx = _ctx(browser, client, viewport={'width': 390, 'height': 844}, reduced_motion='reduce')
    page = ctx.new_page()
    page.goto('http://testserver/ar/home')
    assert page.locator('#njIntro').is_hidden()
    page.locator('#heroCeo').click(trial=True, timeout=1000)
    ctx.close()
