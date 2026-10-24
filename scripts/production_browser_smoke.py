from playwright.sync_api import sync_playwright, expect

BASE = "https://karmaai.online"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 390, "height": 844})

    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(BASE + "/ar/home", wait_until="networkidle")
    expect(page.locator("body")).to_be_visible()
    assert page.locator('a[href="#"]').count() == 0

    # Site assistant: real public contact CTA opens the widget.
    toggle = page.locator("#saToggle")
    expect(toggle).to_be_visible()
    toggle.click()
    expect(page.locator("#siteAssistant")).to_have_class(lambda c: c and "open" in c)

    # CEO CTA opens the consultation; one harmless live request proves the AI path.
    page.locator("#heroCeo").click()
    expect(page.locator("#ceoProblem")).to_be_visible()
    page.fill("#ceoProblem", "أريد تحسين سرعة الرد على العملاء في متجري بدون مشاركة أي بيانات شخصية")
    page.locator("#ceoSubmit").click()
    page.locator("#ceoResult").wait_for(state="visible", timeout=45000)
    assert page.locator("#ceoAgents li").count() >= 1
    href = page.locator("#ceoSubscribe").get_attribute("href") or ""
    assert href.startswith("/portal?pkg="), href

    # Language navigation is live.
    page.goto(BASE + "/en/home", wait_until="networkidle")
    expect(page.locator("body")).to_have_attribute("data-lang", "en")

    # Portal plan selection opens the registration form.
    page.goto(BASE + "/portal", wait_until="networkidle")
    page.locator(".pkg").first.wait_for(timeout=20000)
    page.locator(".pkg").first.click()
    expect(page.locator("#regForm")).to_be_visible()

    # Login surface exists; anonymous owner page does not expose dashboard.
    page.goto(BASE + "/login", wait_until="networkidle")
    expect(page.locator("body")).to_be_visible()
    response = page.request.get(BASE + "/api/owner/overview")
    assert response.status == 401

    # Contact-page button opens the same site assistant.
    page.goto(BASE + "/ar/contact", wait_until="networkidle")
    page.locator("#contactOpenAssistant").click()
    expect(page.locator("#siteAssistant")).to_have_class(lambda c: c and "open" in c)

    assert not errors, errors
    print("PRODUCTION_BROWSER_SMOKE_PASS")
    browser.close()
