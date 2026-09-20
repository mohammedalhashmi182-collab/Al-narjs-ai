"""Inspect the WhatsApp Business Account via the Graph API.

Usage (run from the project root so ``.env`` is picked up)::

    python scripts/verify_waba.py                          # uses .env WHATSAPP_TOKEN + WHATSAPP_WABA_ID
    python scripts/verify_waba.py --token EA... --waba 1757013252262840

Prints: business info, registered phone numbers (incl. Phone IDs), message
template statuses and business verification capability. Treat the output as
sensitive — phone IDs and IDs are not secrets, but keep the token out of any
logs or commits.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

APP_ID = os.getenv("WHATSAPP_APP_ID", "1084796300950403")
DEFAULT_WABA = os.getenv("WHATSAPP_WABA_ID", "1757013252262840")
GRAPH = "https://graph.facebook.com/v21.0"


def api(token: str, path: str, fields: str | None = None):
    url = f"{GRAPH}{path}?access_token={token}"
    if fields:
        url += f"&fields={urllib.parse.quote(fields)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": {"status": e.code, "body": e.read().decode("utf-8", "replace")[:500]}}


def main() -> int:
    import urllib.parse

    parser = argparse.ArgumentParser(description="Inspect the WhatsApp Business Account via API")
    parser.add_argument("--token", default=None)
    parser.add_argument("--waba", default=DEFAULT_WABA)
    args = parser.parse_args()

    token = args.token or os.getenv("WHATSAPP_TOKEN")
    if not token:
        print("[x] No WHATSAPP_TOKEN found. Pass --token or set it in .env")
        return 2
    print(f"[*] App ID: {APP_ID}  WABA: {args.waba}  token unseen (len={len(token)})")

    info = api(token, f"/{args.waba}", "name,display_name_verified,timezone_id,currency,id")
    print("\n=== Business account ===")
    print(json.dumps(info, ensure_ascii=False, indent=2))

    phones = api(token, f"/{args.waba}/phone_numbers",
                 "display_phone_number,verified_name,code_verification_status,quality_rating,platform_type,id")
    print("\n=== Phone numbers (Phone IDs here) ===")
    print(json.dumps(phones, ensure_ascii=False, indent=2))

    tpl = api(token, f"/{args.waba}/message_templates",
              "name,status,category,language,created_time")
    print("\n=== Message templates ===")
    print(json.dumps(tpl, ensure_ascii=False, indent=2))

    cap = api(token, f"/{args.waba}/business_capability")
    print("\n=== Business capability / verification ===")
    print(json.dumps(cap, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())