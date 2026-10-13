"""Web search for analyst agents behind a small provider abstraction.

The first provider whose key is set wins (order: Tavily, Brave, Serper).
With no key the tool is disabled and says which env var to set.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

TIMEOUT = 10.0
MAX_RESULTS = 5
DISABLED_MESSAGE = (
    "البحث على الويب غير مفعّل بعد. لتفعيله أضف أحد المفاتيح: TAVILY_API_KEY أو BRAVE_SEARCH_API_KEY أو SERPER_API_KEY. "
    "(Web search is disabled: set TAVILY_API_KEY, BRAVE_SEARCH_API_KEY or SERPER_API_KEY.)"
)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str

    def as_dict(self) -> dict:
        return {"title": self.title, "url": self.url, "snippet": self.snippet}


class Provider:
    name = "base"
    env_var = ""

    def __init__(self, key: str):
        self.key = key

    async def search(self, client: httpx.AsyncClient, query: str, n: int) -> list[SearchResult]:
        raise NotImplementedError


class TavilyProvider(Provider):
    name, env_var = "tavily", "TAVILY_API_KEY"

    async def search(self, client, query, n):
        r = await client.post("https://api.tavily.com/search",
                              json={"api_key": self.key, "query": query, "max_results": n})
        r.raise_for_status()
        return [SearchResult(i.get("title", ""), i.get("url", ""), i.get("content", ""))
                for i in (r.json().get("results") or [])]


class BraveProvider(Provider):
    name, env_var = "brave", "BRAVE_SEARCH_API_KEY"

    async def search(self, client, query, n):
        r = await client.get("https://api.search.brave.com/res/v1/web/search",
                             params={"q": query, "count": n},
                             headers={"X-Subscription-Token": self.key, "Accept": "application/json"})
        r.raise_for_status()
        return [SearchResult(i.get("title", ""), i.get("url", ""), i.get("description", ""))
                for i in ((r.json().get("web") or {}).get("results") or [])]


class SerperProvider(Provider):
    name, env_var = "serper", "SERPER_API_KEY"

    async def search(self, client, query, n):
        r = await client.post("https://google.serper.dev/search", json={"q": query, "num": n, "gl": "sa"},
                              headers={"X-API-KEY": self.key})
        r.raise_for_status()
        return [SearchResult(i.get("title", ""), i.get("link", ""), i.get("snippet", ""))
                for i in (r.json().get("organic") or [])]


PROVIDERS: tuple[type[Provider], ...] = (TavilyProvider, BraveProvider, SerperProvider)


def get_provider() -> Provider | None:
    forced = (os.getenv("WEB_SEARCH_PROVIDER") or "").strip().lower()
    for cls in PROVIDERS:
        key = (os.getenv(cls.env_var) or "").strip()
        if key and (not forced or forced == cls.name):
            return cls(key)
    return None


def status() -> dict:
    p = get_provider()
    return {"enabled": p is not None, "provider": p.name if p else None,
            "env_vars": [c.env_var for c in PROVIDERS]}


async def search(query: str, n: int = MAX_RESULTS) -> dict:
    query = (query or "").strip()[:300]
    provider = get_provider()
    if not provider:
        return {"enabled": False, "results": [], "message": DISABLED_MESSAGE}
    if not query:
        return {"enabled": True, "provider": provider.name, "results": [], "message": "empty query"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            results = await provider.search(client, query, max(1, min(n, 10)))
    except Exception as exc:  # network/provider errors never break the agent run
        return {"enabled": True, "provider": provider.name, "results": [],
                "message": f"search failed: {type(exc).__name__}"}
    return {"enabled": True, "provider": provider.name, "results": [r.as_dict() for r in results[:n]]}


def context_block(res: dict) -> str:
    if not res.get("enabled"):
        return "\n\n[أداة البحث على الويب]: " + res.get("message", DISABLED_MESSAGE)
    if not res.get("results"):
        return "\n\n[أداة البحث على الويب]: لا توجد نتائج."
    lines = [f"- {r['title']} — {r['url']}\n  {r['snippet'][:300]}" for r in res["results"]]
    return "\n\n[نتائج بحث ويب حديثة — استشهد بالمصادر]:\n" + "\n".join(lines)
