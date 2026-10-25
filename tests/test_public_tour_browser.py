"""Browser acceptance for the disclosed tour; no provider or payment calls."""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_BROWSER_TESTS") != "1", reason="Opt-in Chromium checks"
)


@pytest.mark.parametrize("width", [320, 390, 768, 1440])
@pytest.mark.parametrize("lang", ["ar", "en"])
def test_tour_keyboard_mobile_and_asset_loading(width, lang):
    from fastapi.testclient import TestClient
    from playwright.sync_api import sync_playwright
    from src.main import app

    with TestClient(app) as client, sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            viewport={"width": width, "height": 844}, reduced_motion="reduce"
        )
        context.add_cookies(
            [{"name": "narjs_consent", "value": "denied", "url": "http://testserver"}]
        )
        context.route("**/*", lambda route: route.abort())

        def serve(route):
            response = client.get(route.request.url.replace("http://testserver", ""))
            route.fulfill(
                status=response.status_code,
                body=response.content,
                headers={"content-type": response.headers.get("content-type", "text/plain")},
            )

        context.route("http://testserver/**", serve)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://testserver/" + lang + "/tour")
        page.locator("#tourRole").filter(
            has_text="المستشار" if lang == "ar" else "consultant"
        ).wait_for()
        assert page.locator(".nt-badge").is_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        assert page.locator("#tourPrev").is_disabled()
        for i in range(1, 6):
            page.locator("#tourNext").click()
            assert (
                page.locator('[data-tour-step="' + str(i) + '"]').get_attribute("aria-current")
                == "step"
            )
            assert page.locator("#tourProgress").inner_text() == str(i + 1) + " / 6"
        assert page.locator("#tourNext").is_disabled()
        page.locator("#tourPrev").focus()
        page.keyboard.press("Enter")
        assert page.locator('[data-tour-step="4"]').get_attribute("aria-current") == "step"
        assert (
            page.locator(".nj-whatsapp-contact")
            .get_attribute("href")
            .startswith("https://wa.me/966540799266?")
        )
        assert page.locator("video").get_attribute("autoplay") is None
        assert page.locator("video track").count() == 2
        for path in [
            "/static/video/narjis-tour-60s.mp4",
            "/static/video/narjis-tour-ar.vtt",
            "/static/video/narjis-tour-en.vtt",
        ]:
            assert client.get(path).status_code == 200
        assert errors == []
        context.close()
        browser.close()
