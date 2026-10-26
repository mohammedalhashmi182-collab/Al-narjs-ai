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
        browser = p.chromium.launch(executable_path=os.environ.get('BROWSER_EXECUTABLE_PATH'))
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
            target = url.path + ('?' + url.query if url.query else '')
            req = route.request
            # forward the real method and body so POST endpoints (the CEO consult) work
            response = client.request(req.method, target, content=req.post_data_buffer,
                                      headers={'content-type': req.headers.get('content-type', 'application/json')})
            route.fulfill(status=response.status_code, body=response.content,
                          headers={'content-type': response.headers.get('content-type', 'text/plain')})
        # Keep browser checks offline too (pytest-socket only covers Python).
        context.route('**/*', lambda route: route.abort())
        context.route('http://testserver/**', serve)
        yield context
        context.close()


def wait_for_preloader(page, timeout=15000):
    """Wait until the landing overlay stops intercepting pointer events.

    The overlay is dismissed by JS on window load +600ms, with a 2400ms timer
    and a 4s CSS failsafe behind it. Clicking before that is a race: on a slow
    CI runner Playwright reports `preloader intercepts pointer events` even
    though the page is correct. Waiting on the computed style rather than on a
    class name keeps this honest whichever path dismissed it.
    """
    page.wait_for_function(
        """() => {
            const p = document.getElementById('preloader');
            if (!p) return true;
            const s = getComputedStyle(p);
            return s.visibility === 'hidden'
                || s.pointerEvents === 'none'
                || s.opacity === '0';
        }""",
        timeout=timeout,
    )


@pytest.mark.parametrize('width', [320, 390, 768, 1440])
@pytest.mark.parametrize('path', ['/home', '/consult', '/portal'])
def test_mobile_pages_and_language_switch(context, width, path):
    from playwright.sync_api import expect
    page = context.new_page()
    page.set_viewport_size({'width': width, 'height': 844})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://testserver' + path)
    wait_for_preloader(page)
    if path == '/portal':
        page.locator('.pkg').first.wait_for()
    for lang in ['ar', 'en']:
        if path in ['/consult', '/portal']:
            with page.expect_navigation(wait_until='load'):
                page.locator('[data-lang-btn="' + lang + '"]').first.click()
            expect(page).to_have_url('http://testserver/' + lang + path)
        else:
            # v2 home: the language is server-rendered at /ar/... or /en/...;
            # the switch for the current language is hidden, so navigate to it.
            page.goto('http://testserver/' + lang + path)
        wait_for_preloader(page)
        expect(page.locator('body')).to_be_visible()
        expect(page.locator('body')).to_have_attribute('data-lang', lang)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert page.locator('a[href="#"]').count() == 0
    if path == '/home':
        tag = page.locator('[data-plan="bidaya"] .tag').bounding_box()
        card = page.locator('[data-plan="bidaya"]').bounding_box()
        assert tag['y'] >= card['y'] and tag['x'] >= card['x']
        assert tag['x'] + tag['width'] <= card['x'] + card['width'] + 1
        # every v2 subscription plan has a /portal?pkg= link; Enterprise is
        # by quote and links to /consult instead
        from src.services import catalog
        assert page.locator('.plans a[href^="/portal?pkg="]').count() == len(catalog.PACKAGE_ORDER)
        for key in catalog.PACKAGE_ORDER:
            assert page.locator('.plans a[href="/portal?pkg=' + key + '"]').count() == 1
        # the consent banner (shown while META_PIXEL_ID is set) is fixed to the
        # bottom of the viewport; answer it the way a visitor would first
        if page.locator('#cookieReject').count():
            page.locator('#cookieReject').click()
        # the hero CEO control is a normal link to the consult page
        failed = []
        page.on('requestfailed', lambda req: failed.append(req.url) if 'testserver' in req.url else None)
        page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' and 'net::ERR_FAILED' not in msg.text else None)
        with page.expect_navigation(wait_until='load') as navigation:
            page.locator('#heroCeo').click()
        response = navigation.value
        assert response is not None and response.ok
        assert urlsplit(page.url).path.rstrip('/').endswith('/consult')
        wait_for_preloader(page)
        expect(page.locator('body')).to_be_visible()
        assert page.locator('body').get_attribute('data-lang') in ('ar', 'en')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert not failed
    if path == '/portal':
        page.locator('.pkg').first.click()
        assert page.locator('#regForm').is_visible()
    assert not errors


def test_portal_timeout_and_retry_preserve_plan(context):
    page = context.new_page()
    page.route('**/api/portal/packages', lambda route: None)
    page.clock.install()
    page.goto('http://testserver/portal?pkg=bidaya')
    assert page.locator('.package-skeleton').count() == 3
    page.clock.fast_forward(5100)
    page.locator('#retry-packages').wait_for()
    assert page.locator('#pkg-grid').get_attribute('aria-busy') == 'false'
    assert page.locator('#retry-packages').get_attribute('href') == '/portal?pkg=bidaya'
    page.unroute('**/api/portal/packages')
    page.locator('#retry-packages').click()
    page.locator('.pkg.selected').wait_for()
    assert page.locator('.pkg.selected').get_attribute('data-pkg') == 'bidaya'


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
        page.route('**/*', lambda route: route.abort())
        page.route('http://testserver/**', serve)
        page.goto('http://testserver/home')
        counters = page.locator('#team .facts b[data-target]').all()
        assert len(counters) >= 2
        for counter in counters:
            assert int(counter.inner_text()) > 0
        assert page.locator('#team').is_visible()
        assert page.locator('#team details.dv').count() > 0
        assert page.locator('#pricing .plan').count() == 3
        assert page.locator('#team .rv').first.evaluate('(el) => getComputedStyle(el).opacity') == '1'
        page.close()
