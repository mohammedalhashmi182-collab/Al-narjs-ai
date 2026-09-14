from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.parse
from dataclasses import dataclass

import httpx

from src.utils.logger import get_logger

logger = get_logger(__name__)

LINKEDIN_UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"
LINKEDIN_SCOPE = "w_member_social w_organization_social"
X_TWEETS_URL = "https://api.x.com/2/tweets"
X_MAX_CHARS = 280
TRUNCATE_SUFFIX = "..."

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_TOO_MANY_REQUESTS = 429

_LINKEDIN_ENV = ("LINKEDIN_ACCESS_TOKEN", "LINKEDIN_ORG_ID")
_X_ENV = (
    "X_CONSUMER_KEY",
    "X_CONSUMER_SECRET",
    "X_ACCESS_TOKEN",
    "X_ACCESS_TOKEN_SECRET",
)


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _percent_encode(value: str) -> str:
    return urllib.parse.quote(str(value), safe="-._~")


def _truncate(text: str, limit: int = X_MAX_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = limit - len(TRUNCATE_SUFFIX)
    return f"{text[:cut].rstrip()}{TRUNCATE_SUFFIX}"


def _org_urn(org_id: str) -> str:
    org_id = org_id.strip()
    if org_id.startswith("urn:"):
        return org_id
    return f"urn:li:organization:{org_id}"


def _linkedin_payload(text: str, org_id: str, link: str | None) -> dict[str, object]:
    share_content: dict[str, object] = {"shareCommentary": {"text": text}}
    if link:
        share_content["shareMediaCategory"] = "ARTICLE"
        share_content["media"] = [
            {
                "status": "READY",
                "description": {"text": text[:200]},
                "originalUrl": link,
                "title": {"text": text[:200]},
            }
        ]
    else:
        share_content["shareMediaCategory"] = "NONE"
    return {
        "author": _org_urn(org_id),
        "lifecycleState": "PUBLISHED",
        "specificContent": {"com.linkedin.ugc.ShareContent": share_content},
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }


@dataclass(frozen=True)
class XCredentials:
    consumer_key: str
    consumer_secret: str
    access_token: str
    access_token_secret: str


def _build_oauth_header(
    *,
    method: str,
    base_url: str,
    query_params: dict[str, str],
    creds: XCredentials,
) -> dict[str, str]:
    oauth_params: dict[str, str] = {
        "oauth_consumer_key": creds.consumer_key,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": creds.access_token,
        "oauth_version": "1.0",
    }
    params = {**oauth_params, **{k: v for k, v in query_params.items() if k not in oauth_params}}
    encoded = {_percent_encode(k): _percent_encode(v) for k, v in params.items()}
    param_string = "&".join(f"{k}={v}" for k, v in sorted(encoded.items()))
    base_string = "&".join(
        [method.upper(), _percent_encode(base_url), _percent_encode(param_string)]
    )
    signing_key = (
        f"{_percent_encode(creds.consumer_secret)}&{_percent_encode(creds.access_token_secret)}"
    )
    digest = hmac.new(
        signing_key.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    oauth_params["oauth_signature"] = base64.b64encode(digest).decode("utf-8")
    header = ", ".join(
        f'{_percent_encode(k)}="{_percent_encode(v)}"' for k, v in oauth_params.items()
    )
    return {"Authorization": f"OAuth {header}"}


def _linkedin_error(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        return f"HTTP {resp.status_code}"
    if resp.status_code == HTTP_TOO_MANY_REQUESTS:
        retry_after = resp.headers.get("retry-after") or resp.headers.get("retryAfter")
        message = f"LinkedIn rate limit (HTTP {HTTP_TOO_MANY_REQUESTS})"
        if retry_after:
            message = f"{message}, retry after {retry_after}s"
        return message
    message = body.get("message")
    if message:
        return str(message)
    return f"HTTP {resp.status_code}: {resp.text[:200]}"


def _twitter_error(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        return f"HTTP {resp.status_code}"
    if resp.status_code == HTTP_TOO_MANY_REQUESTS:
        reset = resp.headers.get("x-rate-limit-reset")
        message = f"X API rate limit (HTTP {HTTP_TOO_MANY_REQUESTS})"
        if reset:
            message = f"{message}, resets at epoch {reset}"
        return message
    errors = body.get("errors")
    if isinstance(errors, list) and errors:
        extracted = [
            str(item["message"])
            for item in errors
            if isinstance(item, dict) and item.get("message")
        ]
        if extracted:
            return "; ".join(extracted)
    detail = body.get("detail") or body.get("message")
    if detail:
        return str(detail)
    return f"HTTP {resp.status_code}: {resp.text[:200]}"


async def publish_to_linkedin(text: str, link: str | None = None) -> dict[str, str | bool]:
    token = _env("LINKEDIN_ACCESS_TOKEN")
    org_id = _env("LINKEDIN_ORG_ID")
    if not token or not org_id:
        logger.warning(
            "LinkedIn not configured — missing LINKEDIN_ACCESS_TOKEN / LINKEDIN_ORG_ID"
        )
        return {
            "success": False,
            "url": "",
            "error": "LINKEDIN_ACCESS_TOKEN and LINKEDIN_ORG_ID must be set",
        }
    payload = _linkedin_payload(text, org_id, link)
    headers: dict[str, str] = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(LINKEDIN_UGC_POSTS_URL, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        logger.exception("LinkedIn publish network timeout")
        return {"success": False, "url": "", "error": f"Network timeout: {exc}"}
    except httpx.HTTPError as exc:
        logger.exception("LinkedIn publish network error")
        return {"success": False, "url": "", "error": f"Network error: {exc}"}
    except Exception as exc:
        logger.exception("LinkedIn publish unexpected error")
        return {"success": False, "url": "", "error": f"Unexpected error: {exc}"}

    if resp.status_code in (HTTP_OK, HTTP_CREATED):
        post_id = str((resp.json() or {}).get("id") or "")
        if post_id.startswith("urn:li:share:"):
            post_id = post_id.replace("urn:li:share:", "urn:li:ugcPost:", 1)
        url = f"https://www.linkedin.com/feed/update/{post_id}"
        logger.info("LinkedIn post published: %s", url)
        return {"success": True, "url": url, "error": ""}
    error = _linkedin_error(resp)
    logger.error("LinkedIn publish failed (%s): %s", resp.status_code, error)
    return {"success": False, "url": "", "error": error}


async def publish_to_twitter(text: str) -> dict[str, str | bool]:
    consumer_key = _env("X_CONSUMER_KEY")
    consumer_secret = _env("X_CONSUMER_SECRET")
    access_token = _env("X_ACCESS_TOKEN")
    access_token_secret = _env("X_ACCESS_TOKEN_SECRET")
    if not all((consumer_key, consumer_secret, access_token, access_token_secret)):
        logger.warning("X API not configured — missing X API credentials")
        return {
            "success": False,
            "url": "",
            "error": "X_CONSUMER_KEY, X_CONSUMER_SECRET, X_ACCESS_TOKEN, "
            "X_ACCESS_TOKEN_SECRET must be set",
        }
    body = _truncate(text, X_MAX_CHARS)
    if not body:
        return {"success": False, "url": "", "error": "Tweet text is empty after truncation"}
    creds = XCredentials(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )
    query: dict[str, str] = {"expansions": "author_id", "user.fields": "username"}
    url = f"{X_TWEETS_URL}?{urllib.parse.urlencode(query)}"
    try:
        headers = _build_oauth_header(
            method="POST",
            base_url=X_TWEETS_URL,
            query_params=query,
            creds=creds,
        )
        headers["Content-Type"] = "application/json"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json={"text": body})
    except httpx.TimeoutException as exc:
        logger.exception("Tweet publish network timeout")
        return {"success": False, "url": "", "error": f"Network timeout: {exc}"}
    except Exception as exc:
        logger.exception("Tweet publish failed")
        return {"success": False, "url": "", "error": f"Unexpected error: {exc}"}

    if resp.status_code in (HTTP_OK, HTTP_CREATED):
        data = resp.json() or {}
        tweet_id = str(data.get("data", {}).get("id") or "")
        username = ""
        users = data.get("includes", {}).get("users") or []
        if users:
            username = str(users[0].get("username") or "")
        if username:
            url = f"https://x.com/{username}/status/{tweet_id}"
        else:
            url = f"https://x.com/i/web/status/{tweet_id}"
        logger.info("Tweet published: %s", url)
        return {"success": True, "url": url, "error": ""}
    error = _twitter_error(resp)
    logger.error("Tweet publish failed (%s): %s", resp.status_code, error)
    return {"success": False, "url": "", "error": error}


async def publish_to_all(text: str, link: str | None = None) -> dict[str, dict[str, str | bool]]:
    linkedin = await publish_to_linkedin(text, link)
    twitter = await publish_to_twitter(text)
    return {"linkedin": linkedin, "twitter": twitter}


def check_config() -> dict[str, object]:
    linkedin_missing = [name for name in _LINKEDIN_ENV if not _env(name)]
    twitter_missing = [name for name in _X_ENV if not _env(name)]
    return {
        "linkedin": {
            "configured": not linkedin_missing,
            "missing": linkedin_missing,
        },
        "twitter": {
            "configured": not twitter_missing,
            "missing": twitter_missing,
        },
        "ready": not linkedin_missing and not twitter_missing,
    }


if __name__ == "__main__":
    from src.utils.logger import configure_logging

    configure_logging(level="INFO")
    status = check_config()
    print(json.dumps(status, indent=2, ensure_ascii=False))
