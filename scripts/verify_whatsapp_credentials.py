"""Validate the Meta WhatsApp Cloud API credentials stored in ``.env``.

Usage (run from the project root so ``.env`` is picked up)::

    python scripts/verify_whatsapp_credentials.py
    python scripts/verify_whatsapp_credentials.py --graph-version v23.0
    python scripts/verify_whatsapp_credentials.py --json

It performs three read-only checks against the Graph API — no message is ever
sent, nothing in the website is touched:

1. ``/debug_token`` — is the token valid, does it expire, which scopes does it
   hold. If the token cannot introspect itself and an app id/secret pair exists,
   the check is retried with that app access token instead.
2. ``/<PHONE_ID>`` — does this token really reach that number, what is its
   display number, is it verified, what is its quality rating.
3. ``/<WABA_ID>`` (only when present) — the account review status, which is what
   actually gates live sending.

On success it prints a green confirmation; on failure it prints the exact Meta
error code together with the concrete fix. The token is never printed: output is
limited to its length, the granted scopes, the public display number and Meta's
own status fields.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
GRAPH_HOST = "https://graph.facebook.com"
DEFAULT_VERSION = "v21.0"
VERSION_FALLBACKS = ("v23.0", "v22.0", "v20.0", "v19.0")
DEFAULT_TIMEOUT = 20

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
DIM = "\033[2m"
BOLD = "\033[1m"
OFF = "\033[0m"

SUCCESS_LINE = "تم التحقق.. الرقم مربوط وجاهز للتشغيل والأتمتة بنجاح!"

PHONE_FIELDS = (
    "id,display_phone_number,verified_name,quality_rating,"
    "code_verification_status,status,is_official_business_account"
)
WABA_FIELDS = "id,account_review_status,name"

# Meta error code -> (short Arabic reason, concrete fix). Codes are the ones that
# actually occur when a token/phone pair is wrong; anything else falls back to
# Meta's own message.
ERROR_GUIDE: dict[str, tuple[str, str]] = {
    "0": (
        "تعذر الاتصال بخادم Meta",
        "تحقق من الإنترنت/الوكيل (proxy) ثم أعد المحاولة. هذا فحص محلي بلا اتصال.",
    ),
    "10": (
        "صلاحية غير كافية (Permission denied)",
        "التطبيق لا يملك صلاحية whatsapp_business_messaging، أو هو في وضع Development "
        "ولم يُراجع بعد. من Business Manager: Settings → Accounts → WhatsApp Accounts "
        "أضف الرقم، ومن System User أعِد توليد التوكن بالصلاحيتين "
        "whatsapp_business_messaging + whatsapp_business_management.",
    ),
    "33": (
        "معرّف العنصر غير موجود (Phone Number ID غير صحيح)",
        "انسخ الرقم من Meta Business Suite → WhatsApp Manager → API Setup ← "
        "WhatsApp Business Account ID، وتأكد أنه يبدأ بأرقام فقط وليس اسم الحساب.",
    ),
    "100": (
        "معامل غير صالح (Invalid parameter)",
        "راجع صيغة الـ Phone Number ID (أرقام فقط) وأن الإصدار المطلوب مدعوم؛ "
        "جرّب --graph-version بج إصدار أحدث.",
    ),
    "190": (
        "التوكن غير صالح أو منتهي الصلاحية",
        "أنشئ Permanent Token جديدًا: Business Manager → Users → System Users → "
        "Generate New Token، مع الصلاحيات whatsapp_business_messaging و"
        "whatsapp_business_management، ثم حدّث WHATSAPP_TOKEN في .env.",
    ),
    "200": (
        "الصلاحية غير مفعّلة بعد (API Permission Denied)",
        "التطبيق لم يمر على المراجعة أو لم تُمنح الصلاحيات بعد. أكمل Application Review "
        "واربط التطبيق بحساب WhatsApp Business، ثم أعد المحاولة.",
    ),
    "294": (
        "يلزم إعادة تفويض (Re-authorization required)",
        "التوكن يحتاج إعادة إنشاء من System User بالتوكن الجديد (الCause: re-authentication).",
    ),
    "803": (
        "المسار غير معروف (Unknown path components)",
        "الـ Phone Number ID لا ينتمي لهذا التطبيق/الحساب. تأكد نسخه من الحساب الصحيح "
        "ومن التطبيق الصحيح في Business Manager.",
    ),
    "131047": (
        "انتهت صلاحية الجلسة (Re-authentication required)",
        "ولّد توكنًا جديدًا من System User وضعه في .env.",
    ),
}

_UNSUPPORTED_VERSION = re.compile(
    r"unsupported\s+(get\s+request|api\s+version)|version\s+v?\d+\.\d+\s+is\s+not|"
    r"unknown\s+version|unsupported\s+get",
    re.IGNORECASE,
)


class Colors:
    """Tiny colour switch so piped/``--no-color`` output stays clean."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def __call__(self, code: str, text: str) -> str:
        return f"{code}{text}{OFF}" if self.enabled else text


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #


def load_env_file(path: Path) -> dict[str, str]:
    """Parse a ``KEY=VALUE`` env file. Comments and blanks are ignored."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key:
            values[key] = value.strip().strip('"').strip("'")
    return values


def resolve_credentials(env_file: dict[str, str], environ: dict[str, str] | None = None) -> dict[str, str]:
    """Real environment variables win over the ``.env`` file."""
    environ = os.environ if environ is None else environ

    def pick(key: str) -> str:
        return (environ.get(key) or env_file.get(key) or "").strip()

    return {
        "token": pick("WHATSAPP_TOKEN"),
        "phone_id": pick("WHATSAPP_PHONE_ID"),
        "waba_id": pick("WHATSAPP_WABA_ID"),
        "app_id": pick("META_APP_ID") or pick("FACEBOOK_APP_ID"),
        "app_secret": pick("META_APP_SECRET") or pick("FACEBOOK_APP_SECRET"),
        "version": (pick("GRAPH_API_VERSION") or DEFAULT_VERSION).lstrip("v"),
    }


# --------------------------------------------------------------------------- #
# Graph API transport
# --------------------------------------------------------------------------- #

Transport = Callable[[str, dict[str, Any], int], dict[str, Any]]


def urllib_transport(url: str, params: dict[str, Any], timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """GET the Graph API and return decoded JSON — never raises, never echoes secrets."""
    full = f"{url}?{urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})}"
    try:
        with urllib.request.urlopen(full, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"error": {"message": body[:200] or f"HTTP {e.code}", "code": e.code, "type": "http"}}
    except urllib.error.URLError as e:
        return {"error": {"message": f"network: {type(e.reason).__name__}", "code": 0, "type": "network"}}
    except Exception as e:  # noqa: BLE001 - report the type only
        return {"error": {"message": f"transport: {type(e).__name__}", "code": 0, "type": "transport"}}


def _error_of(payload: dict[str, Any]) -> dict[str, Any] | None:
    err = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(err, dict):
        sub = err.get("error_subcode") or err.get("error_data", {}).get("error_subcode")
        return {
            "code": err.get("code", 0),
            "subcode": sub,
            "message": str(err.get("message", ""))[:400],
            "type": err.get("type", ""),
        }
    return None


def _is_unsupported_version(error: dict[str, Any]) -> bool:
    return bool(_UNSUPPORTED_VERSION.search(error.get("message", "")))


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #


def check_token(
    token: str,
    version: str,
    transport: Transport,
    *,
    app_id: str = "",
    app_secret: str = "",
) -> dict[str, Any]:
    """``/debug_token`` introspection. ``available=False`` means it could not run."""
    access = token
    used_app_token = False
    if app_id and app_secret:
        access = f"{app_id}|{app_secret}"

    payload = transport(
        f"{GRAPH_HOST}/{version}/debug_token",
        {"input_token": token, "access_token": access},
        DEFAULT_TIMEOUT,
    )
    error = _error_of(payload)
    if error and not used_app_token and not (app_id and app_secret):
        return {"available": False, "error": error}
    if error:
        # Retry once with the app access token when a pair is configured.
        access = f"{app_id}|{app_secret}"
        used_app_token = True
        payload = transport(
            f"{GRAPH_HOST}/{version}/debug_token",
            {"input_token": token, "access_token": access},
            DEFAULT_TIMEOUT,
        )
        error = _error_of(payload)
    if error:
        return {"available": False, "error": error}

    data = payload.get("data") or {}
    expires_at = data.get("expires_at") or 0
    return {
        "available": True,
        "app_token_used": used_app_token,
        "is_valid": bool(data.get("is_valid")),
        "type": data.get("type", ""),
        "scopes": sorted(data.get("scopes") or []),
        "app_id": str(data.get("app_id") or ""),
        "expires_at": expires_at,
        "expired": _expiry_state(expires_at),
        "needs_reauth": bool(data.get("needs_reauth")),
    }


def _expiry_state(expires_at: Any) -> str:
    """``permanent`` for Meta's 0 (never expires), else the local expiry date."""
    try:
        value = int(expires_at or 0)
    except (TypeError, ValueError):
        return "unknown"
    if value == 0:
        return "permanent"
    stamp = datetime.fromtimestamp(value, tz=timezone.utc).astimezone()
    delta = datetime.fromtimestamp(value, tz=timezone.utc) - datetime.now(timezone.utc)
    days = delta.days
    if days < 0:
        return f"expired ({stamp:%Y-%m-%d})"
    return f"valid until {stamp:%Y-%m-%d} ({days} day(s) left)"


def check_phone(token: str, phone_id: str, version: str, transport: Transport) -> dict[str, Any]:
    """``/<PHONE_ID>`` — proves the token really owns/reaches that number."""
    payload = transport(
        f"{GRAPH_HOST}/{version}/{urllib.parse.quote(phone_id, safe='')}",
        {"fields": PHONE_FIELDS, "access_token": token},
        DEFAULT_TIMEOUT,
    )
    error = _error_of(payload)
    if error:
        return {"ok": False, "error": error}
    return {
        "ok": True,
        "id": str(payload.get("id", "")),
        "display_phone_number": str(payload.get("display_phone_number", "") or ""),
        "verified_name": str(payload.get("verified_name", "") or ""),
        "quality_rating": str(payload.get("quality_rating", "") or ""),
        "code_verification_status": str(payload.get("code_verification_status", "") or ""),
        "status": str(payload.get("status", "") or ""),
        "official": payload.get("is_official_business_account"),
    }


def check_waba(token: str, waba_id: str, version: str, transport: Transport) -> dict[str, Any]:
    """``/<WABA_ID>`` — account review status gates live sending."""
    payload = transport(
        f"{GRAPH_HOST}/{version}/{urllib.parse.quote(waba_id, safe='')}",
        {"fields": WABA_FIELDS, "access_token": token},
        DEFAULT_TIMEOUT,
    )
    error = _error_of(payload)
    if error:
        return {"ok": False, "error": error}
    return {
        "ok": True,
        "id": str(payload.get("id", "")),
        "name": str(payload.get("name", "") or ""),
        "account_review_status": str(payload.get("account_review_status", "") or ""),
    }


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


def guide_for(code: Any, message: str) -> tuple[str, str]:
    """Map a Meta error code (or its text) to a reason + the fix."""
    key = str(code if code not in (None, "") else "0")
    if key in ERROR_GUIDE:
        return ERROR_GUIDE[key]
    lowered = (message or "").lower()
    if "unsupported get request" in lowered and "graph.facebook.com" not in lowered:
        return (
            "المسار غير مدعوم لهذا التوكن",
            "التوكن لا يملك صلاحية whatsapp_business_management، أو الـ Phone ID "
            "لا ينتمي لهذا الحساب. أعد توليد التوكن من System User بالصلاحيتين.",
        )
    if "access token" in lowered and "invalid" in lowered:
        return ERROR_GUIDE["190"]
    if "permission" in lowered:
        return ERROR_GUIDE["10"]
    if "not exist" in lowered or "does not exist" in lowered:
        return ERROR_GUIDE["33"]
    return (
        f"خطأ من Meta: {message[:180] or 'غير محدد'}",
        "انسخ كود الخطأ من الرابط أعلاه وابحث عنه في developers.facebook.com/docs/graph-api/guides/error-handling/",
    )


def token_shape_issue(token: str) -> tuple[bool, str, str]:
    """Pre-flight: does this string even look like a Meta Cloud API token?

    Returns ``(ok, reason, fix)``. This runs before any network call so a wrong
    paste is reported precisely instead of Meta's generic 190.
    """
    if not token:
        return False, "WHATSAPP_TOKEN فارغ", "أضف التوكن في .env"
    if "|" in token:
        left = token.split("|", 1)[0]
        if left.isdigit():
            return (
                False,
                "القيمة صيغة App ID | App Secret وليست WhatsApp Token",
                "هذه الصيغة تُستخدم كـ app access token في Graph فقط ولا تصلح لإرسال رسائل WhatsApp. "
                "انسخ Permanent Token من Business Manager → Users → System Users → "
                "Generate New Token (بصلاحية whatsapp_business_messaging) والصقه في WHATSAPP_TOKEN.",
            )
        return (
            False,
            "القيمة تحتوي على الرمز | فتستبعد أنها توكن Meta",
            "تأكد أن ما لصقته هو توكن Meta كاملًا يبدأ بـ EAA دون أي فاصل أو نص إضافي.",
        )
    if not token.startswith("EAA"):
        return (
            False,
            f"القيمة لا تبدأ بـ EAA (تبدأ بـ {token[:3]!r}) فهي ليست توكن Meta",
            "التوكن الصحيح يكون بصيغة EAA… بطول 200+ حرف. انسخه كاملًا من System User "
            "في Business Manager دون قص أو تعديل.",
        )
    if len(token) < 50:
        return (
            False,
            f"التوكن قصير جدًا ({len(token)} حرف)",
            "توكن Meta الكامل أطول بكثير من ذلك — غالبًا نُسخ بشكل جزئي.",
        )
    return True, "", ""


def phone_id_shape_issue(phone_id: str) -> tuple[bool, str, str]:
    """Pre-flight for the Phone Number ID: Meta ids are long digit strings."""
    if not phone_id:
        return False, "WHATSAPP_PHONE_ID فارغ", "أضف معرّف الرقم في .env"
    if not phone_id.isdigit():
        return (
            False,
            "معرّف الرقم يحتوي حروفًا أو رموزًا",
            "الـ Phone Number ID أرقام فقط (15–16 رقمًا). انسخه من WhatsApp Manager → API Setup.",
        )
    if not 10 <= len(phone_id) <= 20:
        return (
            False,
            f"معرّف الرقم طوله غير متوقع ({len(phone_id)} رقم)",
            "الطول الصحيح 15–16 رقمًا. انسخه من Business Suite → WhatsApp Manager → API Setup.",
        )
    return True, "", ""


def build_report(creds: dict[str, str], transport: Transport) -> dict[str, Any]:
    """Run every check and return a JSON-serialisable report (never raises)."""
    token, phone_id = creds["token"], creds["phone_id"]
    version = creds["version"]
    report: dict[str, Any] = {
        "ok": False,
        "graph_version": version,
        "version_fallback_used": None,
        "token_length": len(token),
        "checks": {},
    }

    shape_ok, shape_reason, shape_fix = token_shape_issue(token)
    if not shape_ok:
        report["failure"] = {
            "stage": "token-shape",
            "code": 0,
            "message": f"token length {len(token)}",
            "reason": shape_reason,
            "fix": shape_fix,
        }
        return report

    phone_id_ok, phone_id_reason, phone_id_fix = phone_id_shape_issue(phone_id)
    if not phone_id_ok:
        report["failure"] = {
            "stage": "phone-shape",
            "code": 0,
            "message": "WHATSAPP_PHONE_ID",
            "reason": phone_id_reason,
            "fix": phone_id_fix,
        }
        return report

    token_info = check_token(
        token, version, transport,
        app_id=creds.get("app_id", ""), app_secret=creds.get("app_secret", ""),
    )
    report["checks"]["token"] = token_info
    if token_info.get("available"):
        if not token_info["is_valid"]:
            report["failure"] = {
                "stage": "token",
                "code": 190,
                "message": token_info["expired"],
                **dict(zip(("reason", "fix"), guide_for(190, "Invalid OAuth access token"))),
            }
            return report
        if token_info["expired"].startswith("expired"):
            report["failure"] = {
                "stage": "token",
                "code": 190,
                "message": token_info["expired"],
                **dict(zip(("reason", "fix"), guide_for(190, "expired token"))),
            }
            return report

    phone = check_phone(token, phone_id, version, transport)
    used_version = version
    candidates = (version,) + tuple(v for v in VERSION_FALLBACKS if v != version)
    for index, candidate in enumerate(candidates):
        if phone.get("ok"):
            break
        error = phone.get("error") or {}
        if _is_unsupported_version(error) and index + 1 < len(candidates):
            used_version = candidates[index + 1]
            report["version_fallback_used"] = used_version
            phone = check_phone(token, phone_id, used_version, transport)
            continue
        break
    report["graph_version"] = used_version

    report["checks"]["phone"] = phone
    if not phone.get("ok"):
        error = phone.get("error") or {}
        code = error.get("code", 0)
        reason, fix = guide_for(code, error.get("message", ""))
        report["failure"] = {
            "stage": "phone",
            "code": code,
            "subcode": error.get("subcode"),
            "message": error.get("message", ""),
            "reason": reason,
            "fix": fix,
        }
        return report

    if creds.get("waba_id"):
        report["checks"]["waba"] = check_waba(token, creds["waba_id"], used_version, transport)

    report["ok"] = True
    return report


def render(report: dict[str, Any], paint: Colors, *, quiet: bool = False) -> None:
    """Print the human report. Never prints the token itself."""
    def out(text: str = "") -> None:
        if not quiet:
            print(text)

    failure = report.get("failure")
    if failure:
        stage_label = {
            "config": "ملف .env",
            "token-shape": "شكل التوكن",
            "phone-shape": "شكل معرّف الرقم",
            "token": "التوكن",
            "phone": "الرقم",
        }.get(str(failure.get("stage")), str(failure.get("stage")))
        out()
        out(paint(RED + BOLD, "  ✗ فشل التحقق"))
        out(paint(RED, f"  المرحلة     : {stage_label}"))
        out(paint(RED, f"  كود Meta    : {failure.get('code')}"
                       f"{' (subcode ' + str(failure['subcode']) + ')' if failure.get('subcode') else ''}"))
        out(paint(RED, f"  السبب       : {failure.get('reason')}"))
        if failure.get("message"):
            out(paint(DIM, f"  رسالة Meta  : {failure['message']}"))
        out()
        out(paint(YELLOW, "  التوجيه الصحيح للإصلاح:"))
        for line in str(failure.get("fix", "")).split(" — "):
            out(f"    • {line.strip()}")
        out()
        return

    out()
    out(paint(GREEN + BOLD, "  ✓ " + SUCCESS_LINE))
    out()
    phone = report["checks"].get("phone", {})
    token_info = report["checks"].get("token", {})
    waba = report["checks"].get("waba") or {}

    out(paint(BOLD, "  تفاصيل الفحص"))
    out(f"    رقم الجوال        : {phone.get('display_phone_number') or '—'}")
    out(f"    الاسم الموثّق     : {phone.get('verified_name') or '—'}")
    out(f"    حالة الترقيم      : {phone.get('code_verification_status') or '—'}")
    out(f"    تقييم الجودة      : {phone.get('quality_rating') or '—'}")
    out(f"    حالة الحساب       : {phone.get('status') or '—'}")
    if waba:
        out(f"    مراجعة الحساب     : {waba.get('account_review_status') or '—'}")
    out()
    out(paint(BOLD, "  التوكن"))
    out(f"    الطول             : {report.get('token_length')} حرف (لا يُطبع)")
    if token_info.get("available"):
        out(f"   Validity          : {token_info.get('type') or '—'}")
        out(f"    الصلاحية          : {token_info.get('expired')}")
        out(f"    الصلاحيات         : {', '.join(token_info.get('scopes') or []) or '—'}")
        out(f"    App ID            : {token_info.get('app_id') or '—'}")
    else:
        out(paint(DIM, "    (لم يعمل debug_token — تم التحقق عبر استدعاء الرقم مباشرة)"))
    if report.get("version_fallback_used"):
        out(paint(DIM, f"  (استُخدم إصدار GraphAPI البديل: {report['version_fallback_used']})"))
    out(paint(DIM, "  Graph API: " + str(report.get("graph_version"))))
    out()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate WHATSAPP_TOKEN + WHATSAPP_PHONE_ID against the Meta Graph API.",
    )
    parser.add_argument("--env-file", default=str(ROOT / ".env"), help="مسار ملف .env (افتراضيًا جذر المشروع)")
    parser.add_argument("--graph-version", default="", help="إصدار Graph API (مثال v23.0)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--json", action="store_true", help="إخراج التقرير بصيغة JSON")
    parser.add_argument("--no-color", action="store_true", help="بدون ألوان")
    args = parser.parse_args(argv)

    paint = Colors(not args.no_color and sys.stdout.isatty() and not args.json)
    env_file = load_env_file(Path(args.env_file))
    creds = resolve_credentials(env_file)
    if args.graph_version:
        creds["version"] = args.graph_version.lstrip("v")

    if not creds["token"] or not creds["phone_id"]:
        missing = [k for k, v in (("WHATSAPP_TOKEN", creds["token"]), ("WHATSAPP_PHONE_ID", creds["phone_id"])) if not v]
        report = {
            "ok": False,
            "failure": {
                "stage": "config",
                "code": 0,
                "message": f"missing in {args.env_file}: {', '.join(missing)}",
                "reason": "بيانات الاعتماد غير موجودة في ملف .env",
                "fix": "أضف السطرين إلى .env: WHATSAPP_TOKEN=<Permanent Token> و"
                       "WHATSAPP_PHONE_ID=<Phone Number ID من Meta Business Suite>",
            },
        }
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            render(report, paint)
        return 1

    transport = lambda url, params, timeout: urllib_transport(url, params, timeout)  # noqa: E731
    report = build_report(creds, transport)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        render(report, paint)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())