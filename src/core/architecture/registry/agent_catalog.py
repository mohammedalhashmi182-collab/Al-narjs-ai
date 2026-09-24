"""Centralized agent catalog for capability matching and dynamic routing.

Loads the system agents once from ``agents/base/*.yaml`` (including the
:code:`x_tasami` operating metadata), tokenizes each identity into searchable
keywords, and answers "which agent can do this task?" deterministically.

The catalog never touches the database and performs no network I/O at import
time, so it is safe to import from anywhere (tests, routers, worker loops).
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = "gemini:gemini-3.6-flash"

_WORD_RE = re.compile(r"[a-zA-Z0-9]{2,}|[\u0600-\u06FF]{2,}", re.UNICODE)
_AR_RE = re.compile(r"[\u0600-\u06FF]")

_STOP: frozenset = frozenset(
    {
        "the", "and", "for", "with", "you", "your", "are", "this", "that",
        "from", "have", "not", "all", "can", "will", "but", "what", "when",
        "how", "also", "into", "them", "they", "then", "than", "their",
    }
)


def _tokenize(text: Any) -> set[str]:
    return {
        t.lower()
        for t in _WORD_RE.findall(str(text or ""))
        if t.lower() not in _STOP
    }


def _has_arabic(text: Any) -> bool:
    return bool(_AR_RE.search(str(text or "")))


@dataclass
class AgentCapability:
    """Searchable identity of one agent, enriched from YAML ``x_tasami``."""

    slug: str
    name: str
    description: str
    category: str
    default_model: str
    code: Optional[str] = None
    dept: Optional[str] = None
    authority: Optional[str] = None
    owner_only: bool = False
    micro_budget_usd: float = 0.0
    modes: List[str] = field(default_factory=list)
    receives_from: List[str] = field(default_factory=list)
    delivers_to: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    source: str = "yaml"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "default_model": self.default_model,
            "code": self.code,
            "dept": self.dept,
            "authority": self.authority,
            "owner_only": self.owner_only,
            "micro_budget_usd": self.micro_budget_usd,
            "modes": list(self.modes),
            "receives_from": list(self.receives_from),
            "delivers_to": list(self.delivers_to),
            "source": self.source,
        }


@dataclass
class CatalogMatch:
    """A scored agent candidate from a matching query."""

    agent: AgentCapability
    score: float
    matched_tokens: List[str] = field(default_factory=list)


class AgentCatalog:
    """In-memory, lazily-loaded catalog of agent capabilities."""

    def __init__(self, base_path: Optional[Path] = None) -> None:
        self._base_path: Path = base_path or Path("agents/base")
        self._entries: Dict[str, AgentCapability] = {}
        self._lock = asyncio.Lock()
        self._loaded_at: float = 0.0

    # -- Loading -------------------------------------------------------------

    def load_dir(self, path: Optional[Path] = None) -> int:
        """Load every ``*.yaml`` under ``path`` (default ``agents/base``)."""
        base = path or self._base_path
        if not base.exists():
            logger.warning("agent_catalog base path missing", path=str(base))
            return 0
        for yaml_file in sorted(base.glob("*.yaml")):
            self.add_from_yaml(yaml_file)
        self._loaded_at = time.time()
        logger.info(
            "agent_catalog loaded", count=len(self._entries), source=str(base)
        )
        return len(self._entries)

    def add_from_yaml(self, yaml_path: Path) -> Optional[AgentCapability]:
        """Parse a single agent YAML into a catalog entry (best-effort)."""
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None
            meta = data.get("x_tasami") or {}
            entry = AgentCapability(
                slug=yaml_path.stem,
                name=str(data.get("name") or yaml_path.stem),
                description=str(data.get("description") or ""),
                category=str(data.get("category") or "general"),
                default_model=str(data.get("model") or DEFAULT_MODEL),
                code=meta.get("code"),
                dept=meta.get("dept"),
                authority=meta.get("authority"),
                owner_only=bool(meta.get("owner_only")),
                micro_budget_usd=float(meta.get("micro_budget_usd") or 0.0),
                modes=[str(m) for m in (meta.get("modes") or [])],
                receives_from=[str(x) for x in (meta.get("receives_from") or [])],
                delivers_to=[str(x) for x in (meta.get("delivers_to") or [])],
                source="yaml",
            )
            entry.keywords = _tokenize(
                f"{entry.name} {entry.description} {entry.category} "
                f"{' '.join(entry.modes)}"
            )
            self._entries[entry.slug] = entry
            return entry
        except Exception as e:  # pragma: no cover - defensive loader
            logger.warning(
                "agent_catalog yaml parse failed",
                path=str(yaml_path),
                error=str(e),
            )
            return None

    async def sync_from_registry(self, agent_registry: Any) -> int:
        """Additively merge agents that live only in the database.

        Never removes or overrides YAML-backed entries; a failure here must not
        prevent startup, so the catalog still works purely from YAML.
        """
        try:
            agents = await agent_registry.list_agents()
            for a in agents:
                if a.slug in self._entries:
                    continue
                entry = AgentCapability(
                    slug=a.slug,
                    name=a.name,
                    description=a.description or "",
                    category=a.category.value
                    if hasattr(a.category, "value")
                    else str(a.category),
                    default_model=a.default_model,
                    source="db",
                )
                entry.keywords = _tokenize(
                    f"{entry.name} {entry.description} {entry.category}"
                )
                self._entries[entry.slug] = entry
            logger.info("agent_catalog db sync", count=len(self._entries))
        except Exception as e:  # pragma: no cover - defensive sync
            logger.warning("agent_catalog db sync failed", error=str(e))
        return len(self._entries)

    # -- Lookups -------------------------------------------------------------

    def get(self, slug: str) -> Optional[AgentCapability]:
        return self._entries.get(slug)

    def all(self) -> List[AgentCapability]:
        return list(self._entries.values())

    def count(self) -> int:
        return len(self._entries)

    def match(
        self,
        task: str,
        lang: Optional[str] = None,
        category: Optional[str] = None,
        top_k: int = 5,
        include_owner_only: bool = False,
    ) -> List[CatalogMatch]:
        """Rank agents by tokenized capability overlap with ``task``.

        Deterministic: ties break alphabetically by slug. Owner-only agents are
        excluded from public routing unless explicitly requested.
        """
        if not self._entries:
            self.load_dir()
        tokens = _tokenize(task)
        if not tokens:
            return []

        scored: List[CatalogMatch] = []
        for entry in self._entries.values():
            if entry.owner_only and not include_owner_only:
                continue
            entry_tokens: set[str] = set(entry.keywords)
            matched = tokens & entry_tokens
            if not matched:
                continue
            score = float(len(matched))
            if entry.slug in tokens:
                score += 1.0
            elif entry.name and _tokenize(entry.name) & tokens:
                score += 0.5
            if category and entry.category == category:
                score += 1.0
            if lang == "ar" and _has_arabic(entry.description):
                score += 0.25
            if _has_arabic(task) and not _has_arabic(entry.description):
                score -= 0.25

            scored.append(
                CatalogMatch(
                    agent=entry,
                    score=round(score, 3),
                    matched_tokens=sorted(matched),
                )
            )

        scored.sort(key=lambda m: (-m.score, m.agent.slug))
        return scored[:top_k]

    def best_match(
        self,
        task: str,
        lang: Optional[str] = None,
        category: Optional[str] = None,
        include_owner_only: bool = False,
    ) -> Optional[CatalogMatch]:
        matches = self.match(
            task,
            lang=lang,
            category=category,
            top_k=1,
            include_owner_only=include_owner_only,
        )
        return matches[0] if matches else None

    def fallback(self) -> AgentCapability:
        """Deterministic default agent for capability misses."""
        for slug in ("customer_service", "social_media", "marketing_agent"):
            entry = self._entries.get(slug)
            if entry is not None:
                return entry
        if self._entries:
            return min(self._entries.values(), key=lambda e: e.slug)
        return AgentCapability(
            slug="general",
            name="General Agent",
            description="General purpose assistant",
            category="general",
            default_model=DEFAULT_MODEL,
        )
