"""Register/inspect the Telegram Bot API webhook for the production endpoint.

Usage (run from the project root so ``.env`` is picked up)::

    python scripts/setup_telegram_webhook.py           # setWebhook + getWebhookInfo
    python scripts/setup_telegram_webhook.py --info    # getWebhookInfo only
    python scripts/setup_telegram_webhook.py --delete  # remove the webhook

Requires ``TELEGRAM_TOKEN`` and ``TELEGRAM_WEBHOOK_SECRET`` in ``.env``.
The webhook target defaults to ``https://<DOMAIN>/webhooks/telegram``.

Neither the token nor the secret is ever printed, logged or committed: the
output is limited to lengths, public URLs and Telegram's own status fields.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API = "https://api.telegram.org/bot{token}/{method}"
REDACTED = "<redacted>"


def _redact(text: str, *secrets: str | None) -> str:
    """Strip every known secret out of any string before it reaches stdout."""
    out = str(text)
    for secret in secrets:
        if secret:
            out = out.replace(secret, REDACTED)
    return out


def call(token: str, method: str, params: dict | None = None) -> dict:
    """POST to the Bot API; returns Telegram's JSON (never raising)."""
    url = API.format(token=token, method=method)
    data = urllib.parse.urlencode(params or {}).encode("utf-8")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        return {"ok": False, "error_code": e.code, "description": body}
    except Exception as e:  # noqa: BLE001 - report, never echo the URL
        return {"ok": False, "error_code": 0, "description": type(e).__name__}


def main() -> int:
    from src.config.settings import settings

    parser = argparse.ArgumentParser(description="Telegram webhook registration")
    parser.add_argument("--url", default=None, help="Override the webhook target URL")
    parser.add_argument("--info", action="store_true", help="Only show getWebhookInfo")
    parser.add_argument("--delete", action="store_true", help="Remove the webhook")
    args = parser.parse_args()

    token = settings.telegram_token
    secret = settings.telegram_webhook_secret
    if not token:
        print("[x] TELEGRAM_TOKEN is not set in .env")
        return 2
    print(f"[*] token <set len={len(token)}>, secret <set len={len(secret or 0)}> (values unseen)")

    if args.delete:
        res = call(token, "deleteWebhook")
        print(f"[{'+' if res.get('ok') else 'x'}] deleteWebhook: {_redact(res, token, secret)}")
        return 0 if res.get("ok") else 1

    if not args.info:
        target = args.url or f"https://{settings.domain}/webhooks/telegram"
        params = {"url": target, "allowed_updates": json.dumps(["message"])}
        if secret:
            params["secret_token"] = secret
        else:
            print("[!] TELEGRAM_WEBHOOK_SECRET missing — registering without a secret is unsafe")
        res = call(token, "setWebhook", params)
        if not res.get("ok"):
            print(f"[x] setWebhook failed: {_redact(res, token, secret)}")
            return 1
        print(f"[+] setWebhook ok -> {target}")

    info = call(token, "getWebhookInfo")
    if not info.get("ok"):
        print(f"[x] getWebhookInfo failed: {_redact(info, token, secret)}")
        return 1
    r = info.get("result", {})
    print(
        "[*] webhook info: "
        f"url_set={bool(r.get('url'))} pending={r.get('pending_update_count', 0)} "
        f"last_error={_redact(r.get('last_error_message') or '-', token, secret)}"
    )
    return 0


if __name__ == "__main__":
    os.chdir(ROOT)
    raise SystemExit(main())
