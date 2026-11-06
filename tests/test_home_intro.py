"""Home opens on the voice consultant, with no intro overlay.

Run with RUN_BROWSER_TESTS=1.
"""
import os
from urllib.parse import urlsplit

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_BROWSER_TESTS") != "1",
    reason="set RUN_BROWSER_TESTS=1 for Chromium checks",
)


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("BROWSER_EXECUTABLE_PATH")
        )
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from src.main import app

    with TestClient(app) as test_client:
        yield test_client


def _ctx(browser, client, **kwargs):
    ctx = browser.new_context(**kwargs)

    def serve(route):
        url = urlsplit(route.request.url)
        response = client.request(
            route.request.method,
            url.path + ("?" + url.query if url.query else ""),
            content=route.request.post_data_buffer,
        )
        route.fulfill(
            status=response.status_code,
            body=response.content,
            headers={"content-type": response.headers.get("content-type", "text/plain")},
        )

    ctx.route("**/*", lambda route: route.abort())
    ctx.route("http://testserver/**", serve)
    return ctx


def _errors(page):
    errs = []
    page.on("pageerror", lambda error: errs.append(str(error)))
    page.on(
        "console",
        lambda message: message.type == "error"
        and "net::ERR_FAILED" not in message.text
        and errs.append(message.text),
    )
    return errs


@pytest.mark.parametrize("lang,width", [("ar", 390), ("ar", 1440), ("en", 390), ("en", 1440)])
def test_home_shows_the_consultant_without_an_intro(browser, client, lang, width):
    ctx = _ctx(browser, client, viewport={"width": width, "height": 844})
    page = ctx.new_page()
    errs = _errors(page)
    page.add_init_script(
        """
        window.__micCalls = 0;
        const devices = navigator.mediaDevices || {};
        devices.getUserMedia = function () {
          window.__micCalls += 1;
          return Promise.reject(new DOMException('denied', 'NotAllowedError'));
        };
        navigator.mediaDevices = devices;
        """
    )
    with page.expect_response(lambda response: response.url.endswith("/api/voice/status")):
        page.goto(f"http://testserver/{lang}/home")
    assert page.locator("#njIntro, #intro, #preloader, .nj-intro, .preloader").count() == 0
    consultant = page.locator("#voiceConsultant")
    assert consultant.is_visible()
    box = consultant.bounding_box()
    hero = page.locator("#top").bounding_box()
    assert box["y"] < 8
    assert box["y"] < hero["y"]
    assert box["height"] >= page.viewport_size["height"] * 0.85
    assert page.locator("#start").is_visible()
    assert page.locator("#chat").is_visible()
    assert page.locator("#voiceOrb").is_visible()
    assert page.locator(".scroll-hint").is_visible()
    assert page.locator("#chatPanel").is_hidden()
    if lang == "ar":
        assert "مستشار النرجس" in consultant.inner_text()
        assert page.locator("#chat").inner_text().strip() == "دردشة"
    else:
        assert "Al-Narjis advisor" in consultant.inner_text()
        assert page.locator("#chat").inner_text().strip() == "Chat"
    assert page.evaluate("window.__micCalls") == 0
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    assert "790" in page.locator("#pricing").inner_text()
    assert "1,490" in page.locator("#pricing").inner_text()
    assert "2,990" in page.locator("#pricing").inner_text()
    assert errs == []
    ctx.close()
