"""Pre-deploy guard: is the public landing page actually visible?

Static tests cannot answer this. A page can have a correct status code, a
complete DOM, every token in place, and still be unusable because one opaque
element is painted over the entire viewport. That is exactly how the preloader
incident shipped: 200, full markup, tests green, blank page.

This script asks the only question that matters to a visitor: is the thing at
the centre of the screen the page, or a cover?

    python scripts/verify_page_visible.py [url] [--screenshot out.png]

Exits 0 when the page is visible, 1 when something covers it, 2 when the check
could not run (no browser, page unreachable). It is deliberately separate from
the pytest suite because it needs a real browser, which CI does not have; run
it locally against a production deploy before trusting a layout change.

    python -m uvicorn src.main:app --port 8011
    python scripts/verify_page_visible.py http://127.0.0.1:8011/home
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]

# A full-viewport, fully painted, hit-testable layer over the centre of the
# screen means the visitor is looking at a cover, not at the site.
PROBE = r"""
(() => {
  const report = [];
  document.querySelectorAll('body *').forEach((el) => {
    const cs = getComputedStyle(el);
    if (cs.position !== 'fixed' && cs.position !== 'absolute') return;
    if (cs.display === 'none') return;
    if (cs.visibility === 'hidden') return;
    if (parseFloat(cs.opacity) < 0.02) return;
    const r = el.getBoundingClientRect();
    if (r.width < window.innerWidth - 20 || r.height < window.innerHeight - 20) return;
    const bg = cs.backgroundColor;
    if (bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent') return;
    const cx = Math.min(Math.max(window.innerWidth / 2, r.left), r.right - 1);
    const cy = Math.min(Math.max(window.innerHeight / 2, r.top), r.bottom - 1);
    const top = document.elementFromPoint(cx, cy);
    if (!top || !el.contains(top)) return;
    report.push(
      el.tagName.toLowerCase() +
      (el.id ? '#' + el.id : '') +
      (typeof el.className === 'string' && el.className
        ? '.' + el.className.split(' ').filter(Boolean)[0]
        : '') +
      '  z=' + cs.zIndex + ' bg=' + bg
    );
  });
  return report;
})()
"""


def find_chrome() -> str | None:
    for candidate in CHROME_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    return shutil.which("google-chrome") or shutil.which("chromium")


def reach(url: str, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status < 500:
                    return True
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


async def probe(chrome: str, url: str, port: int, screenshot: str | None) -> tuple[list[str], str]:
    import websockets

    profile = tempfile.mkdtemp(prefix="narjis-visibility-")
    proc = subprocess.Popen(
        [
            chrome, "--headless=new", f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
            "--window-size=1440,1000", "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        def http_json(path: str):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
                return json.loads(r.read().decode())

        for _ in range(60):
            try:
                http_json("/json/version")
                break
            except Exception:
                time.sleep(0.5)
        target = next(t for t in http_json("/json/list") if t["type"] == "page")

        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=80_000_000) as ws:
            counter = [0]

            async def send(method: str, **params):
                counter[0] += 1
                await ws.send(json.dumps({"id": counter[0], "method": method, "params": params}))
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("id") == counter[0]:
                        if "error" in msg:
                            raise RuntimeError(f"{method}: {msg['error']}")
                        return msg.get("result", {})

            async def evaluate(expression: str):
                result = await send(
                    "Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True
                )
                if result.get("exceptionDetails"):
                    raise RuntimeError(str(result["exceptionDetails"])[:300])
                return result["result"].get("value")

            await send("Page.enable")
            await send("Runtime.enable")
            await send(
                "Emulation.setDeviceMetricsOverride",
                width=1440, height=1000, deviceScaleFactor=1, mobile=False,
            )
            await send("Page.navigate", url=url)
            await asyncio.sleep(6)
            covers = await evaluate(PROBE)
            if screenshot:
                shot = await send("Page.captureScreenshot", format="png")
                with open(screenshot, "wb") as handle:
                    handle.write(base64.b64decode(shot["data"]))
            return covers, url
    finally:
        proc.terminate()
        shutil.rmtree(profile, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", default="https://karmaai.online/home")
    parser.add_argument("--screenshot", default=None, help="also save a PNG here")
    parser.add_argument("--port", type=int, default=9377)
    args = parser.parse_args()

    chrome = find_chrome()
    if not chrome:
        print("SKIP: no Chrome/Chromium found, cannot judge visibility", file=sys.stderr)
        return 2
    if not reach(args.url):
        print(f"SKIP: {args.url} did not answer", file=sys.stderr)
        return 2

    try:
        covers, _ = asyncio.run(probe(chrome, args.url, args.port, args.screenshot))
    except Exception as exc:  # noqa: BLE001 - a broken harness must not read as a pass
        print(f"SKIP: visibility check could not run: {exc}", file=sys.stderr)
        return 2

    if covers:
        print(f"FAIL: {args.url} is covered by a full-viewport layer:", file=sys.stderr)
        for entry in covers:
            print(f"  - {entry}", file=sys.stderr)
        print("  the visitor sees the cover, not the page", file=sys.stderr)
        return 1

    print(f"OK: {args.url} is visible, nothing covers the viewport")
    if args.screenshot:
        print(f"   screenshot: {args.screenshot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
