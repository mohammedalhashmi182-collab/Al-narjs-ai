"""Zid Merchant API client.

Docs:
* OAuth: https://docs.zid.sa/authorization
* Orders: https://docs.zid.sa/list-of-orders
* Products: https://docs.zid.sa/retrieve-a-list-of-products
* Store: https://docs.zid.sa/store-33664558e0
* Profile: https://docs.zid.sa/get-manager-profile

Product calls send ``Access-Token`` (same value as ``X-Manager-Token``) and
``Role: Manager``, which the product API requires.
"""

from __future__ import annotations

import logging
from typing import Optional

from src.integrations import http
from src.integrations.config import env
from src.integrations.parse import amount, ident, number, text
from src.integrations.phones import masked
from src.integrations.provider import OrderHit, ProductHit, StoreApiError, StoreInfo

log = logging.getLogger(__name__)

AUTH_URL = "https://oauth.zid.sa/oauth/authorize"
TOKEN_URL = "https://oauth.zid.sa/oauth/token"
API = "https://api.zid.sa/v1"


def _json(resp, operation: str) -> dict:
    if resp.status_code >= 400:
        log.warning("zid %s failed status=%s", operation, resp.status_code)
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

    client_id, redirect = env("ZID_CLIENT_ID"), env("ZID_REDIRECT_URI")
    if not (client_id and redirect and state):
        return None
    query = urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect,
        "state": state,
    })
    return f"{AUTH_URL}?{query}"


async def _token(form: dict) -> dict:
    if not form.get("client_id") or not form.get("client_secret"):
        raise StoreApiError("oauth_not_configured", 503)
    resp = await http.request("POST", TOKEN_URL, data=form)
    return _json(resp, "token")


async def exchange_code(code: str) -> dict:
    return await _token({
        "grant_type": "authorization_code",
        "code": code,
        "client_id": env("ZID_CLIENT_ID"),
        "client_secret": env("ZID_CLIENT_SECRET"),
        "redirect_uri": env("ZID_REDIRECT_URI"),
    })


async def refresh_tokens(refresh_token: str) -> dict:
    return await _token({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": env("ZID_CLIENT_ID"),
        "client_secret": env("ZID_CLIENT_SECRET"),
        "redirect_uri": env("ZID_REDIRECT_URI"),
    })


def _headers(access_token: str, authorization: str, *, products: bool = False) -> dict:
    headers = {
        "Authorization": f"Bearer {authorization}",
        "X-Manager-Token": access_token,
        "Accept": "application/json",
        "Accept-Language": "ar",
    }
    if products:
        headers["Access-Token"] = access_token
        headers["Role"] = "Manager"
    return headers


def _identity(body: dict) -> StoreInfo:
    node = body
    for key in ("store", "data"):
        inner = node.get(key) if isinstance(node, dict) else None
        if isinstance(inner, dict):
            node = inner.get("store") if isinstance(inner.get("store"), dict) else inner
            break
    if not isinstance(node, dict):
        node = {}
    name = text(node.get("name") or node.get("title") or node.get("store_name")) or None
    return StoreInfo(
        merchant_id=ident(node.get("id") or node.get("store_id")) or "",
        store_ref=ident(node.get("uuid") or node.get("store_uuid")),
        name=name,
        platform="zid",
    )


class ZidClient:
    platform = "zid"

    def __init__(self, access_token: str, authorization: str) -> None:
        self._access = access_token
        self._authorization = authorization

    async def fetch_store(self) -> StoreInfo:
        resp = await http.request(
            "GET", f"{API}/managers/account/store", headers=_headers(self._access, self._authorization),
        )
        if resp.status_code == 404:
            resp = await http.request(
                "GET", f"{API}/managers/account/profile", headers=_headers(self._access, self._authorization),
            )
        info = _identity(_json(resp, "store"))
        if info.merchant_id or info.store_ref:
            return info
        resp = await http.request(
            "GET", f"{API}/managers/account/profile", headers=_headers(self._access, self._authorization),
        )
        return _identity(_json(resp, "profile"))

    async def fetch_order(self, reference: str) -> Optional[OrderHit]:
        resp = await http.request(
            "GET",
            f"{API}/managers/store/orders",
            headers=_headers(self._access, self._authorization),
            params={"search_term": reference, "payload_type": "simple", "per_page": 5},
        )
        body = _json(resp, "orders")
        rows = body.get("orders")
        if isinstance(rows, dict):
            rows = rows.get("orders") or rows.get("data")
        if not isinstance(rows, list):
            rows = body.get("data") if isinstance(body.get("data"), list) else []
        want = reference.casefold()
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = str(row.get("code") or "")
            if want not in {code.casefold(), str(row.get("id") or ""), str(row.get("invoice_number") or "")}:
                continue
            customer = row.get("customer") if isinstance(row.get("customer"), dict) else {}
            phone = str(customer.get("mobile") or customer.get("phone") or "")
            status = row.get("order_status") if isinstance(row.get("order_status"), dict) else row.get("display_status")
            label = text(status.get("name") if isinstance(status, dict) else status)
            return OrderHit(reference=code or reference, status=label, phone=phone, masked=masked(phone), platform=self.platform)
        return None

    async def search_products(self, query: str) -> list[ProductHit]:
        resp = await http.request(
            "GET",
            f"{API}/products/",
            headers=_headers(self._access, self._authorization, products=True),
            params={"search": query, "page_size": 10},
        )
        body = _json(resp, "products")
        rows = body.get("results") or body.get("products") or []
        if not isinstance(rows, list):
            return []
        found: list[ProductHit] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if row.get("is_published") is False:
                continue
            name = text(row.get("name"))[:120]
            if not name:
                continue
            qty = number(row.get("quantity"))
            available = bool(row.get("is_infinite")) or (qty is not None and qty > 0)
            price = amount(row.get("sale_price") if row.get("sale_price") not in (None, "") else row.get("price"))
            found.append(ProductHit(name=name, price=price, available=available, platform=self.platform))
        return found
