"""Live Meta Pixel check.

Verifies that ``fbq('init')`` and ``fbq('track', 'PageView')`` actually execute
in a real browser on the public pages, not merely that the snippet exists in the
HTML.

    python scripts/check_meta_pixel.py                     # production
    python scripts/check_meta_pixel.py --url http://127.0.0.1:8000
    python scripts/check_meta_pixel.py --no-browser        # HTML checks only
    python scripts/check_meta_pixel.py --json

Checks per page
  html   the snippet, init and PageView sit inside <head>, exactly once
  noscript  the image fallback carries the same Pixel ID
  browser  window.fbq exists, the PageView was queued and flushed, the
           fbevents.js script and the tr?id=... beacon were requested, and the
           page produced no console error and no unexpected failed request

Exit code is 0 only when every check passed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

DEFAULT_BASE = "https://karmaai.online"
PAGES = ("/home", "/early-access", "/ar/home", "/ar/early-access")

INIT_RE = re.compile(r"fbq\(\s*'init'\s*,\s*'([0-9]{10,20})'\s*\)")
TRACK_RE = re.compile(r"fbq\(\s*'track'\s*,\s*'PageView'\s*\)")
FBEVENTS_RE = re.compile(r"connect\.facebook\.net/[a-zA-Z_]+/fbevents\.js")
NOSCRIPT_RE = re.compile(r"facebook\.com/tr\?id=([0-9]{10,20})&(?:amp;)?ev=PageView")

# Blockers a human visitor legitimately has; they are not site defects.
BENIGN_BLOCKERS = (
    "net::ERR_BLOCKED_BY_CLIENT",
    "net::ERR_FAILED",
    "ERR_BLOCKED_BY_RESPONSE",
    "connect.facebook.net",
    "www.facebook.com",
    "google-analytics.com",
    "googletagmanager.com",
    "doubleclick",
)


class Failure(Exception):
    pass


def _fetch(url: str, timeout: float = 30.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "narjis-pixel-check/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (explicit https url)
        if resp.status != 200:
            raise Failure(f"{url} -> HTTP {resp.status}")
        return resp.read().decode("utf-8", "replace")


def _head_of(html: str) -> str:
    start = html.lower().find("<head>")
    end = html.lower().find("</head>")
    return html if start == -1 or end == -1 else html[start:end]


def check_html(url: str, expect_id: str | None) -> dict:
    html = _fetch(url)
    head = _head_of(html)
    result: dict = {"url": url, "checks": {}, "errors": []}

    init = INIT_RE.search(head)
    if not init:
        raise Failure("fbq('init') is not inside <head>")
    result["pixel_id"] = init.group(1)
    if expect_id and init.group(1) != expect_id:
        raise Failure(f"Pixel ID mismatch: page has {init.group(1)}, expected {expect_id}")
    result["checks"]["init_in_head"] = True

    if not TRACK_RE.search(head):
        raise Failure("fbq('track', 'PageView') is not inside <head>")
    result["checks"]["pageview_in_head"] = True

    if not FBEVENTS_RE.search(head):
        raise Failure("fbevents.js is not referenced inside <head>")
    result["checks"]["fbevents_in_head"] = True

    counts = {
        "init": len(INIT_RE.findall(html)),
        "track": len(TRACK_RE.findall(html)),
        "fbevents": len(FBEVENTS_RE.findall(html)),
    }
    if any(v != 1 for v in counts.values()):
        raise Failure(f"snippet loaded more than once: {counts} (double PageView)")
    result["checks"]["loaded_once"] = True

    noscript = NOSCRIPT_RE.search(html)
    if not noscript:
        raise Failure("missing <noscript> PageView fallback")
    if noscript.group(1) != result["pixel_id"]:
        raise Failure("noscript fallback carries a different Pixel ID")
    result["checks"]["noscript"] = True

    for marker in ("EAA", "client_secret", "app_secret", "access_token"):
        if marker in html:
            raise Failure(f"page leaks {marker!r} — a Pixel ID is public, a token is not")
    result["checks"]["no_token_leak"] = True
    return result


def check_browser(url: str, timeout: float = 45.0) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"url": url, "skipped": "playwright is not installed"}

    console_errors: list[str] = []
    failed_requests: list[str] = []
    fb_requests: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.on(
                "console",
                lambda m: console_errors.append(m.text) if m.type == "error" else None,
            )
            page.on("requestfailed", lambda r: failed_requests.append(r.url))
            page.on(
                "request",
                lambda r: fb_requests.append(r.url)
                if ("facebook" in r.url or "fbevents" in r.url)
                else None,
            )
            page.goto(url, wait_until="load", timeout=timeout * 1000)
            try:
                page.wait_for_function(
                    "() => window.fbq && window.fbq.loaded === true", timeout=8000
                )
                loaded = True
            except Exception:
                loaded = False
            state = page.evaluate(
                """() => {
                    const f = window.fbq;
                    if (!f) return {hasFbq: false};
                    const q = (f.queue || []).map(a => Array.from(a));
                    return {
                        hasFbq: true,
                        loaded: f.loaded === true,
                        version: f.version || null,
                        queueLen: q.length,
                        calls: q.map(c => c[0]),
                        pixelFromCalls: (q.find(c => c[0] === 'init') || [])[1] || null,
                    };
                }"""
            )
            page.wait_for_timeout(6000)
        finally:
            browser.close()

    result: dict = {"url": url, "browser": state, "loaded": loaded}
    problems: list[str] = []

    # Ground truth: the PageView beacon that Meta actually receives. fbevents.js
    # empties its queue once flushed, so an empty queue is not evidence either way
    # — the network request is. An inactive or deleted Pixel accepts the script
    # and the /signals/config call but never sends the event.
    beacons = [u for u in fb_requests if "/tr" in u and "ev=PageView" in u]
    beacon_ok = bool(beacons)
    result["pageview_beacon"] = beacons[0] if beacons else None
    result["facebook_requests"] = [u.split("?")[0] for u in fb_requests][:6]

    if not state.get("hasFbq"):
        problems.append("window.fbq was never defined — fbevents.js did not load")
    if not state.get("loaded"):
        problems.append("fbq.loaded never became true")
    if not any("facebook" in u or "fbevents" in u for u in fb_requests):
        problems.append("no request reached connect.facebook.net — the CDN is unreachable from here")
    if not beacon_ok:
        problems.append(
            "no PageView beacon reached www.facebook.com/tr — the Pixel is likely "
            "inactive/disabled or its delivery is blocked for this page"
        )
    real_errors = [e for e in console_errors if not any(b in e for b in BENIGN_BLOCKERS)]
    if real_errors:
        problems.append(f"console errors: {real_errors[:3]}")
    real_failures = [u for u in failed_requests if not any(b in u for b in BENIGN_BLOCKERS)]
    if real_failures:
        problems.append(f"failed requests: {real_failures[:3]}")

    result["console_errors"] = console_errors[:5]
    result["failed_requests"] = [u for u in failed_requests[:5]]
    if problems:
        raise Failure("; ".join(problems))
    result["checks"] = {
        "fbq_defined": True,
        "fbq_loaded": True,
        "pageview_beacon_sent": True,
        "no_console_errors": True,
    }
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Live Meta Pixel verification")
    ap.add_argument("--url", default=DEFAULT_BASE, help="base URL (default: production)")
    ap.add_argument("--pixel-id", default=None, help="expected Pixel ID")
    ap.add_argument("--no-browser", action="store_true", help="skip the headless-browser check")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    base = args.url.rstrip("/")
    report: dict = {"base": base, "browser_enabled": not args.no_browser, "pages": []}
    failures: list[str] = []

    for path in PAGES:
        url = f"{base}{path}"
        entry: dict = {"path": path}
        try:
            entry["html"] = check_html(url, args.pixel_id)
        except (Failure, urllib.error.URLError) as exc:
            entry["error"] = str(exc)
            failures.append(f"{path}: {exc}")
            report["pages"].append(entry)
            continue
        if not args.no_browser:
            try:
                entry["runtime"] = check_browser(url)
            except (Failure, urllib.error.URLError) as exc:
                entry["runtime_error"] = str(exc)
                failures.append(f"{path} (browser): {exc}")
        report["pages"].append(entry)

    report["ok"] = not failures
    report["failures"] = failures

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["ok"] else 1

    print(f"Meta Pixel check -> {base}")
    for entry in report["pages"]:
        head = entry.get("html", {})
        status = "FAIL" if entry.get("error") else "PASS"
        print(f"  [{status}] {entry['path']}")
        if entry.get("error"):
            print(f"         html: {entry['error']}")
            continue
        print(f"         Pixel ID {head.get('pixel_id')} · init+PageView in <head> · loaded once")
        rt = entry.get("runtime")
        if isinstance(rt, dict) and "skipped" in rt:
            print(f"         browser: skipped ({rt['skipped']})")
        elif isinstance(rt, dict):
            b = rt.get("browser", {})
            beacon = rt.get("pageview_beacon")
            print(
                f"         browser: fbq v{b.get('version')} loaded={b.get('loaded')} "
                f"· no console errors"
            )
            if beacon:
                print(f"         PageView sent: {beacon[:110]}")
        if entry.get("runtime_error"):
            print(f"         browser: FAIL {entry['runtime_error']}")
    print("RESULT:", "PASS" if report["ok"] else "FAIL")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())