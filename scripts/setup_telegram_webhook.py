"""Register/inspect the Telegram Bot API webhook for the production endpoint.

Usage (run from the project root so ``.env`` is picked up)::

    python scripts/setup_telegram_webhook.py           # auto-select accepted secret + setWebhook
    python scripts/setup_telegram_webhook.py --info    # getWebhookInfo only
    python scripts/setup_telegram_webhook.py --delete  # remove the webhook

Requires ``TELEGRAM_TOKEN`` in ``.env``. The webhook target defaults to
``https://<DOMAIN>/webhooks/telegram``.

Registration picks the first secret the receiver accepts, probed with a
side-effect-free POST (``[]`` answers 400 after a valid secret, 403 otherwise),
so it works whether the server uses ``TELEGRAM_WEBHOOK_SECRET`` or a derived
candidate. Neither the token nor any secret is ever printed, logged or
committed: the output is limited to lengths, source labels, public URLs and
Telegram's own status fields.
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


def _probe(target: str, secret: str) -> str:
    """Ask the receiver whether it accepts ``secret`` — no payload side effects.

    ``400`` = secret accepted (payload rejected as non-dict), ``403`` = rejected,
    ``200`` = receiver disabled, ``0`` = transport failure.
    """
    req = urllib.request.Request(
        target,
        data=b"[]",
        headers={
            "Content-Type": "application/json",
            "X-Telegram-Bot-Api-Secret-Token": secret,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return str(r.status)
    except urllib.error.HTTPError as e:
        return str(e.code)
    except Exception:
        return "0"


def _select_secret(target: str, settings) -> tuple[str, str] | None:
    """First (source label, value) the target receiver accepts, if any."""
    from src.services.telegram_webhook import derived_secrets

    candidates: list[tuple[str, str]] = []
    if settings.telegram_webhook_secret:
        candidates.append(("env", settings.telegram_webhook_secret))
    candidates += [(f"derived[{i}]", v) for i, v in enumerate(derived_secrets())]

    disabled_seen = False
    for label, value in candidates:
        code = _probe(target, value)
        if code == "400":
            print(f"[+] receiver accepts: {label} <len={len(value)}> (value unseen)")
            return label, value
        if code == "200":
            disabled_seen = True
        print(f"[-] {label}: not accepted (probe={code})")
    if disabled_seen:
        print("[x] receiver is disabled on the target — set TELEGRAM_WEBHOOK_SECRET there")
    return None


def main() -> int:
    from src.config.settings import settings

    parser = argparse.ArgumentParser(description="Telegram webhook registration")
    parser.add_argument("--url", default=None, help="Override the webhook target URL")
    parser.add_argument("--info", action="store_true", help="Only show getWebhookInfo")
    parser.add_argument("--delete", action="store_true", help="Remove the webhook")
    args = parser.parse_args()

    token = settings.telegram_token
    if not token:
        print("[x] TELEGRAM_TOKEN is not set in .env")
        return 2
    print(f"[*] token <set len={len(token)}> (value unseen)")

    if args.delete:
        res = call(token, "deleteWebhook")
        print(f"[{'+' if res.get('ok') else 'x'}] deleteWebhook: {_redact(res, token, settings.telegram_webhook_secret)}")
        return 0 if res.get("ok") else 1

    target = args.url or f"https://{settings.domain}/webhooks/telegram"

    secret: str | None = None
    if not args.info:
        selected = _select_secret(target, settings)
        if selected is None:
            return 1
        secret = selected[1]
        params = {"url": target, "allowed_updates": json.dumps(["message"])}
        params["secret_token"] = secret
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
