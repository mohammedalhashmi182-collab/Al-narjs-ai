"""Browser acceptance for #43. Run with RUN_BROWSER_TESTS=1 python -m pytest.

CI installs Chromium. Normal backend-only runs do not require a browser.
All first-party requests are served by TestClient; no production writes occur.
"""
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
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def context(browser):
    from fastapi.testclient import TestClient
    from src.main import app
    with TestClient(app) as client:
        context = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True,
                                      reduced_motion='reduce')
        def serve(route):
            url = urlsplit(route.request.url)
            response = client.get(url.path + ('?' + url.query if url.query else ''))
            route.fulfill(status=response.status_code, body=response.content,
                          headers={'content-type': response.headers.get('content-type', 'text/plain')})
        context.route('http://testserver/**', serve)
        yield context
        context.close()


@pytest.mark.parametrize('width', [320, 390])
@pytest.mark.parametrize('path', ['/home', '/consult', '/portal'])
def test_mobile_pages_and_language_switch(context, width, path):
    page = context.new_page()
    page.set_viewport_size({'width': width, 'height': 844})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://testserver' + path)
    if path == '/portal':
        page.locator('.pkg').first.wait_for()
    for lang in ['ar', 'en']:
        page.locator('[data-lang-btn="' + lang + '"]').first.click()
        assert page.locator('body').is_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert page.locator('a[href="#"]').count() == 0
    if path == '/home':
        tag = page.locator('#plan-social .tag').bounding_box()
        card = page.locator('#plan-social').bounding_box()
        assert tag['y'] >= card['y'] and tag['x'] >= card['x']
        assert tag['x'] + tag['width'] <= card['x'] + card['width'] + 1
        assert page.locator('.pricing-grid a[href*="?start=plan_"]').count() == 4
        page.locator('.mob-cta a[href="/consult"]').click()
        assert urlsplit(page.url).path == '/consult'
    if path == '/portal':
        page.locator('.pkg').first.click()
        assert page.locator('#regForm').is_visible()
    assert not errors


def test_portal_timeout_and_retry_preserve_plan(context):
    page = context.new_page()
    page.route('**/api/portal/packages', lambda route: None)
    page.clock.install()
    page.goto('http://testserver/portal?pkg=social')
    assert page.locator('.package-skeleton').count() == 4
    page.clock.fast_forward(5100)
    page.locator('#retry-packages').wait_for()
    assert page.locator('#pkg-grid').get_attribute('aria-busy') == 'false'
    assert page.locator('#retry-packages').get_attribute('href') == '/portal?pkg=social'
    page.unroute('**/api/portal/packages')
    page.locator('#retry-packages').click()
    page.locator('.pkg.selected').wait_for()
    assert page.locator('.pkg.selected').get_attribute('data-pkg') == 'social'


def test_portal_http_failure(context):
    page = context.new_page()
    page.route('**/api/portal/packages', lambda route: route.fulfill(status=503, body='unavailable'))
    page.goto('http://testserver/portal')
    page.locator('#retry-packages').wait_for()
    assert page.locator('.package-skeleton').count() == 0


def test_home_without_javascript(browser):
    from fastapi.testclient import TestClient
    from src.main import app
    with TestClient(app) as client:
        page = browser.new_page(java_script_enabled=False, viewport={'width': 390, 'height': 844})
        def serve(route):
            response = client.get(urlsplit(route.request.url).path)
            route.fulfill(status=response.status_code, body=response.content,
                          headers={'content-type': response.headers.get('content-type', 'text/plain')})
        page.route('http://testserver/**', serve)
        page.goto('http://testserver/home')
        for counter in page.locator('.stats .num').all():
            assert int(counter.inner_text()) > 0
        assert page.locator('#agents').is_visible()
        assert page.locator('.dv-card').count() > 0
        assert page.locator('#agents .reveal').first.evaluate('(el) => getComputedStyle(el).opacity') == '1'
        page.close()
