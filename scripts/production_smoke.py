from __future__ import annotations
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://karmaai.online"
TIMEOUT = 15
UA = "Al-Narjis-Production-Smoke/1.0"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def fetch(path: str, *, follow: bool = True):
    url = urllib.parse.urljoin(BASE, path)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(req, timeout=TIMEOUT) as r:
            return r.status, r.geturl(), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.geturl(), e.read().decode("utf-8", "replace")

def retry(path: str, expected=(200,), attempts: int = 18, delay: int = 10):
    last = None
    for i in range(attempts):
        last = fetch(path)
        if last[0] in expected:
            return last
        print(f"retry {i + 1}/{attempts} {path}: HTTP {last[0]}", flush=True)
        time.sleep(delay)
    raise AssertionError(f"{path}: expected {expected}, got {last[0] if last else 'no response'}")

def must(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)

status, _, body = retry("/health")
must(status == 200, "/health not 200")
health = json.loads(body)
must(health.get("status") == "healthy", f"health={health!r}")

for path, marker in [
    ("/ar/home", "النرجس"),
    ("/en/home", "Al-Narjis"),
    ("/portal", "portal"),
    ("/login", "login"),
    ("/ar/contact", "مساعد النرجس"),
    ("/ar/pricing", "الباقات"),
    ("/ar/privacy", "الخصوصية"),
    ("/ar/terms", "الشروط"),
    ("/ar/data-deletion", "حذف"),
    ("/ar/about", "الجهة المشغّلة"),
]:
    status, _, body = retry(path)
    must(marker.lower() in body.lower(), f"{path}: missing marker {marker!r}")

for path in ("/ar/home", "/ar/contact", "/ar/pricing"):
    _, _, body = retry(path)
    must("AlNarjisai@gmail.com" not in body, f"{path}: old public email still live")
    must("0540799266" not in body, f"{path}: old public phone still live")

for path in ("/docs", "/redoc", "/openapi.json"):
    status, _, _ = fetch(path)
    must(status == 404, f"{path}: expected 404 in production, got {status}")

status, _, _ = fetch("/api/owner/overview", follow=False)
must(status == 401, f"owner API must be 401 anonymous, got {status}")
status, _, _ = fetch("/owner", follow=False)
must(status in (301, 302, 303, 307), f"/owner must redirect anonymous, got {status}")

_, _, body = retry("/api/portal/session?probe=1")
must(json.loads(body) == {"authenticated": False}, f"portal probe unexpected: {body[:200]!r}")

_, _, body = retry("/api/payments/capabilities")
caps = json.loads(body)
must(caps.get("card") is False, f"Moyasar card unexpectedly live: {caps!r}")

channel_summary = {}
for path, name in (("/webhooks/telegram/health", "telegram"), ("/webhooks/whatsapp/health", "whatsapp")):
    _, _, body = retry(path)
    data = json.loads(body)
    must(isinstance(data, dict), f"{path}: not an object")
    blob = json.dumps(data).lower()
    must("eaa" not in blob and "sk_live_" not in blob and "pk_live_" not in blob,
         f"{path}: credential-like value leaked")
    channel_summary[name] = {
        "configured": data.get("configured"),
        "connected": data.get("connected"),
        "status": data.get("status"),
    }

_, _, deep_body = retry("/health?deep=1")
deep = json.loads(deep_body)
db = deep.get("db") or {}
external = deep.get("external") or {}
must(db.get("ok") is True, f"production DB deep health failed: {db!r}")

print("PRODUCTION_SMOKE_PASS")
print(json.dumps({
    "health": "healthy",
    "public_pages": "ok",
    "owner_isolation": "ok",
    "portal_probe": "ok",
    "database": {"ok": db.get("ok")},
    "externals": {
        name: {
            "configured": (external.get(name) or {}).get("configured"),
            "ok": (external.get(name) or {}).get("ok"),
            "status": (external.get(name) or {}).get("status"),
        }
        for name in ("gemini", "telegram", "whatsapp", "moyasar")
    },
    "moyasar_card": caps.get("card"),
    "channels": channel_summary,
}, ensure_ascii=False))
