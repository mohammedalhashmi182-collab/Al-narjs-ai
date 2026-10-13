"""Read-only Salla and Zid connectors for the store manager agent.

Only GET requests for products and orders. Credentials come from env vars:

* Salla: SALLA_ACCESS_TOKEN (merchant OAuth access token). SALLA_CLIENT_ID /
  SALLA_CLIENT_SECRET / SALLA_REDIRECT_URI are only needed to run the OAuth
  install flow that produces that token (``authorize_url`` / ``exchange_code``).
* Zid: ZID_AUTHORIZATION_TOKEN + ZID_MANAGER_TOKEN (both returned by Zid's
  OAuth token endpoint) and ZID_STORE_ID. ZID_CLIENT_ID / ZID_CLIENT_SECRET /
  ZID_REDIRECT_URI for the OAuth flow.

Without credentials a connector reports ``configured: False`` and a message
naming the missing vars; nothing is called.
"""

from __future__ import annotations

import os
from urllib.parse import urlencode

import httpx

TIMEOUT = 12.0
LIMIT = 20


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


class StoreConnector:
    platform = "base"
    required: tuple[str, ...] = ()
    oauth_vars: tuple[str, ...] = ()
    authorize_endpoint = ""
    token_endpoint = ""

    def missing(self) -> list[str]:
        return [v for v in self.required if not _env(v)]

    def configured(self) -> bool:
        return not self.missing()

    def status(self) -> dict:
        return {"configured": self.configured(), "missing": self.missing(),
                "oauth_ready": all(_env(v) for v in self.oauth_vars)}

    def authorize_url(self, state: str) -> str | None:
        prefix = self.platform.upper()
        cid, redirect = _env(f"{prefix}_CLIENT_ID"), _env(f"{prefix}_REDIRECT_URI")
        if not (cid and redirect):
            return None
        q = {"client_id": cid, "redirect_uri": redirect, "response_type": "code", "state": state}
        if self.platform == "salla":
            q["scope"] = "offline_access"
        return f"{self.authorize_endpoint}?{urlencode(q)}"

    async def exchange_code(self, code: str) -> dict:
        """OAuth code -> tokens. Returned to the owner to store as env vars; never logged."""
        prefix = self.platform.upper()
        data = {"grant_type": "authorization_code", "code": code,
                "client_id": _env(f"{prefix}_CLIENT_ID"), "client_secret": _env(f"{prefix}_CLIENT_SECRET"),
                "redirect_uri": _env(f"{prefix}_REDIRECT_URI")}
        if not all(data.values()):
            raise RuntimeError(f"{prefix} OAuth not configured")
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(self.token_endpoint, data=data)
            r.raise_for_status()
            return r.json()

    def _headers(self) -> dict:
        raise NotImplementedError

    async def _get(self, url: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(url, params=params or {}, headers=self._headers())
            r.raise_for_status()
            return r.json()

    async def products(self) -> list[dict]:
        raise NotImplementedError

    async def orders(self) -> list[dict]:
        raise NotImplementedError

    async def snapshot(self) -> dict:
        if not self.configured():
            return {"platform": self.platform, "configured": False, "missing": self.missing(),
                    "message": f"ربط {self.platform} غير مفعّل — أضف: {', '.join(self.missing())}"}
        try:
            return {"platform": self.platform, "configured": True,
                    "products": await self.products(), "orders": await self.orders()}
        except Exception as exc:
            return {"platform": self.platform, "configured": True, "error": type(exc).__name__,
                    "message": "تعذّر جلب بيانات المتجر"}


class SallaConnector(StoreConnector):
    platform = "salla"
    required = ("SALLA_ACCESS_TOKEN",)
    oauth_vars = ("SALLA_CLIENT_ID", "SALLA_CLIENT_SECRET", "SALLA_REDIRECT_URI")
    authorize_endpoint = "https://accounts.salla.sa/oauth2/auth"
    token_endpoint = "https://accounts.salla.sa/oauth2/token"
    base = "https://api.salla.dev/admin/v2"

    def _headers(self):
        return {"Authorization": f"Bearer {_env('SALLA_ACCESS_TOKEN')}", "Accept": "application/json"}

    async def products(self):
        data = await self._get(f"{self.base}/products", {"per_page": LIMIT})
        return [{"id": p.get("id"), "name": p.get("name"), "price": (p.get("price") or {}).get("amount"),
                 "quantity": p.get("quantity"), "status": p.get("status")} for p in data.get("data") or []]

    async def orders(self):
        data = await self._get(f"{self.base}/orders", {"per_page": LIMIT})
        return [{"id": o.get("id"), "reference": o.get("reference_id"),
                 "total": ((o.get("total") or {}).get("amount")), "status": (o.get("status") or {}).get("name"),
                 "date": (o.get("date") or {}).get("date")} for o in data.get("data") or []]


class ZidConnector(StoreConnector):
    platform = "zid"
    required = ("ZID_AUTHORIZATION_TOKEN", "ZID_MANAGER_TOKEN", "ZID_STORE_ID")
    oauth_vars = ("ZID_CLIENT_ID", "ZID_CLIENT_SECRET", "ZID_REDIRECT_URI")
    authorize_endpoint = "https://oauth.zid.sa/oauth/authorize"
    token_endpoint = "https://oauth.zid.sa/oauth/token"
    base = "https://api.zid.sa/v1"

    def _headers(self):
        return {"Authorization": f"Bearer {_env('ZID_AUTHORIZATION_TOKEN')}",
                "X-Manager-Token": _env("ZID_MANAGER_TOKEN"), "Store-Id": _env("ZID_STORE_ID"),
                "Accept-Language": "ar", "Accept": "application/json"}

    async def products(self):
        data = await self._get(f"{self.base}/products/", {"page_size": LIMIT})
        items = data.get("results") or data.get("products") or []
        return [{"id": p.get("id"), "name": p.get("name"), "price": p.get("price"),
                 "quantity": p.get("quantity"), "status": "published" if p.get("is_published") else p.get("status")}
                for p in items]

    async def orders(self):
        data = await self._get(f"{self.base}/managers/store/orders", {"per_page": LIMIT})
        return [{"id": o.get("id"), "reference": o.get("code"), "total": o.get("order_total"),
                 "status": (o.get("order_status") or {}).get("name") if isinstance(o.get("order_status"), dict)
                 else o.get("order_status"), "date": o.get("created_at")} for o in data.get("orders") or []]


CONNECTORS: dict[str, type[StoreConnector]] = {"salla": SallaConnector, "zid": ZidConnector}


def get(platform: str) -> StoreConnector:
    if platform not in CONNECTORS:
        raise KeyError(platform)
    return CONNECTORS[platform]()


def status() -> dict:
    return {k: c().status() for k, c in CONNECTORS.items()}


async def snapshots() -> list[dict]:
    """Snapshots for every configured store (none configured -> one explanatory entry per platform)."""
    return [await c().snapshot() for c in CONNECTORS.values()]


def context_block(snaps: list[dict]) -> str:
    parts = ["\n\n[بيانات المتجر (قراءة فقط)]:"]
    for s in snaps:
        if not s.get("configured") or s.get("error"):
            parts.append(f"• {s['platform']}: {s.get('message')}")
            continue
        parts.append(f"• {s['platform']}: {len(s['products'])} منتج، {len(s['orders'])} طلب حديث")
        for p in s["products"][:15]:
            parts.append(f"  - منتج: {p.get('name')} | السعر {p.get('price')} ريال | الكمية {p.get('quantity')} | {p.get('status')}")
        for o in s["orders"][:10]:
            parts.append(f"  - طلب {o.get('reference') or o.get('id')}: {o.get('total')} ريال | {o.get('status')} | {o.get('date')}")
    return "\n".join(parts)
