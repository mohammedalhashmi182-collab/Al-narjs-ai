"""Salla Merchant API client.

Docs:
* OAuth: https://docs.salla.dev/authorization
* User info: https://docs.salla.dev/merchants/user-info
* Store info: https://docs.salla.dev/merchants/store-info
* Orders: https://docs.salla.dev/orders/list
* Products: https://docs.salla.dev/product/list-product
"""

from __future__ import annotations

import logging
from typing import Optional

from src.integrations import http
from src.integrations.config import SALLA_SCOPES, env
from src.integrations.parse import amount, ident, number, text
from src.integrations.phones import masked
from src.integrations.provider import OrderHit, ProductHit, StoreApiError, StoreInfo

log = logging.getLogger(__name__)

AUTH_URL = "https://accounts.salla.sa/oauth2/auth"
TOKEN_URL = "https://accounts.salla.sa/oauth2/token"
USER_INFO_URL = "https://accounts.salla.sa/oauth2/user/info"
API = "https://api.salla.dev/admin/v2"


def _json(resp, operation: str) -> dict:
    if resp.status_code >= 400:
        log.warning("salla %s failed status=%s", operation, resp.status_code)
        from src.services import error_monitor

        error_monitor.report("salla", error_type=f"http_{resp.status_code}", message=operation, route=operation)
        raise StoreApiError(operation, resp.status_code)
    try:
        body = resp.json()
    except Exception as exc:
        raise StoreApiError(operation, resp.status_code) from exc
    if not isinstance(body, dict):
        raise StoreApiError(operation, resp.status_code)
    return body


def authorize_url(state: str) -> Optional[str]:
    from urllib.parse import urlencode

    client_id, redirect = env("SALLA_CLIENT_ID"), env("SALLA_REDIRECT_URI")
    if not (client_id and redirect and state):
        return None
    query = urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect,
        "scope": SALLA_SCOPES,
        "state": state,
    })
    return f"{AUTH_URL}?{query}"


async def exchange_code(code: str) -> dict:
    body = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": env("SALLA_CLIENT_ID"),
        "client_secret": env("SALLA_CLIENT_SECRET"),
        "redirect_uri": env("SALLA_REDIRECT_URI"),
    }
    if not all(body.values()):
        raise StoreApiError("oauth_not_configured", 503)
    resp = await http.request("POST", TOKEN_URL, data=body)
    return _json(resp, "token")


async def refresh_tokens(refresh_token: str) -> dict:
    body = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": env("SALLA_CLIENT_ID"),
        "client_secret": env("SALLA_CLIENT_SECRET"),
        "redirect_uri": env("SALLA_REDIRECT_URI"),
    }
    if not body["client_id"] or not body["client_secret"]:
        raise StoreApiError("oauth_not_configured", 503)
    resp = await http.request("POST", TOKEN_URL, data=body)
    return _json(resp, "refresh")


def _bearer(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}


class SallaClient:
    platform = "salla"

    def __init__(self, access_token: str) -> None:
        self._headers = _bearer(access_token)

    async def fetch_store(self) -> StoreInfo:
        resp = await http.request("GET", USER_INFO_URL, headers=self._headers)
        body = _json(resp, "user_info")
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        store = data.get("store") if isinstance(data.get("store"), dict) else {}
        merchant_id = ident(store.get("id")) or ""
        if not merchant_id:
            info = await self._store_info()
            if info.merchant_id:
                return info
        return StoreInfo(merchant_id=merchant_id, store_ref=None, name=text(store.get("name")) or None, platform=self.platform)

    async def _store_info(self) -> StoreInfo:
        resp = await http.request("GET", f"{API}/store/info", headers=self._headers)
        body = _json(resp, "store_info")
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        if isinstance(data.get("store"), dict):
            data = data["store"]
        return StoreInfo(
            merchant_id=ident(data.get("id")) or "",
            store_ref=None,
            name=text(data.get("name")) or None,
            platform=self.platform,
        )

    async def fetch_order(self, reference: str) -> Optional[OrderHit]:
        if not reference.isdigit():
            return None
        resp = await http.request(
            "GET", f"{API}/orders", headers=self._headers, params={"reference_id": reference, "per_page": 5},
        )
        body = _json(resp, "orders")
        rows = body.get("data") if isinstance(body.get("data"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("reference_id") or "") != reference:
                continue
            customer = row.get("customer") if isinstance(row.get("customer"), dict) else {}
            phone = f"{customer.get('mobile_code') or ''}{customer.get('mobile') or ''}"
            status = row.get("status")
            label = text(status.get("name") if isinstance(status, dict) else status)
            return OrderHit(
                reference=reference, status=label, phone=str(phone), masked=masked(phone), platform=self.platform,
            )
        return None

    async def search_products(self, query: str) -> list[ProductHit]:
        resp = await http.request(
            "GET", f"{API}/products", headers=self._headers, params={"keyword": query, "per_page": 10},
        )
        body = _json(resp, "products")
        rows = body.get("data") if isinstance(body.get("data"), list) else []
        found: list[ProductHit] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = text(row.get("name"))[:120]
            if not name:
                continue
            status = str(row.get("status") or "").lower()
            if status in {"hidden", "deleted"}:
                continue
            qty = number(row.get("quantity"))
            available = status != "out" and (qty is None or qty > 0)
            found.append(ProductHit(name=name, price=amount(row.get("price")), available=available, platform=self.platform))
        return found
