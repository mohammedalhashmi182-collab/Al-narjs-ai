"""Owner-started CEO scout.

The owner presses «ابدأ» on the dashboard. The AI CEO leads the agent team and
reads public, already-posted paid demand (freelance projects and remote roles).
Every finding is stored as a draft awaiting approval. This module never sends,
posts, submits, or contacts anyone. Approval only records the owner's decision.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from html import unescape

from sqlalchemy import select

from src.utils.logger import get_logger

logger = get_logger(__name__)

RUN_KEY = "ceo-scout-run"
SOURCE = "ceo_scout"
AWAITING = "awaiting_approval"
MOSTAQL_URL = "https://mostaql.com/projects?sort=latest"
REMOTIVE_URL = "https://remotive.com/api/remote-jobs?search=marketing&limit=15"
_USER_AGENT = "AlNarjisScout/1.0 (+https://alnarjisai.com)"
_PROJECT_RE = re.compile(
    r'<a href="(https://mostaql\.com/project/(\d+)[^"]*)"[^>]*>\s*([^<]+?)\s*</a>',
    re.I,
)
_LOCK = asyncio.Lock()

_MARKETING = ("تسويق", "سوشيال", "اعلان", "إعلان", "محتوى", "marketing", "content", "social", "seo")
_RESEARCH = ("بحث", "دراسة", "research", "analysis")
_BUILD = ("تطوير", "موقع", "برمج", "تصميم", "build", "develop", "website", "design", "n8n", "ذكاء")


def fetch_url(url: str, timeout: float = 12.0) -> str:
    """GET one public page. Callers only pass the two fixed source URLs."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json,text/html;q=0.9"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(1_500_000).decode("utf-8", "replace")


def _agent_for(title: str) -> tuple[str, str]:
    folded = title.casefold()
    if any(word.casefold() in folded for word in _RESEARCH):
        return "research_agent", "وكيل البحث"
    if any(word.casefold() in folded for word in _MARKETING):
        return "marketing_agent", "وكيل التسويق"
    if any(word.casefold() in folded for word in _BUILD):
        return "builder_agent", "وكيل البناء"
    return "ceo", "الرئيس التنفيذي"


def _key_for(url: str) -> str:
    return "scout-" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]


def parse_mostaql(html: str, limit: int = 12) -> list[dict]:
    """Real Mostaql project cards. Titles and URLs come only from the page."""
    found: list[dict] = []
    seen: set[str] = set()
    for match in _PROJECT_RE.finditer(html or ""):
        url, project_id, raw_title = match.group(1), match.group(2), match.group(3)
        if "/project/create" in url or project_id in seen:
            continue
        title = unescape(re.sub(r"\s+", " ", raw_title)).strip()
        if not title or not url.startswith("https://mostaql.com/project/"):
            continue
        seen.add(project_id)
        agent, label = _agent_for(title)
        found.append({
            "title": title[:240],
            "url": url.split("?")[0],
            "source_name": "مستقل",
            "budget": None,
            "company": None,
            "agent": agent,
            "agent_label": label,
        })
        if len(found) >= limit:
            break
    return found


def parse_remotive(payload: str, limit: int = 8) -> list[dict]:
    """Remote roles from Remotive's public JSON. Empty or broken payloads yield nothing."""
    try:
        data = json.loads(payload or "")
    except json.JSONDecodeError:
        return []
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        return []
    found: list[dict] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        url = str(job.get("url") or "").strip()
        title = str(job.get("title") or "").strip()
        if not title or not url.startswith("https://"):
            continue
        salary = str(job.get("salary") or "").strip() or None
        company = str(job.get("company_name") or "").strip() or None
        agent, label = _agent_for(title)
        found.append({
            "title": title[:240],
            "url": url,
            "source_name": "Remotive",
            "budget": salary,
            "company": company,
            "agent": agent,
            "agent_label": label,
        })
        if len(found) >= limit:
            break
    return found


def _public_opportunity(row) -> dict:
    evidence = row.evidence or {}
    return {
        "key": row.key,
        "title": row.title,
        "status": row.status,
        "agent": row.owner_agent,
        "agent_label": evidence.get("agent_label"),
        "source_name": evidence.get("source_name"),
        "source_url": evidence.get("source_url"),
        "budget": evidence.get("budget"),
        "company": evidence.get("company"),
        "sent": False,
        "external_contact": False,
    }


async def _load_run(session):
    from src.models import Opportunity

    return (
        await session.execute(select(Opportunity).where(Opportunity.key == RUN_KEY))
    ).scalar_one_or_none()


async def current_status(session_factory) -> dict:
    from src.models import Opportunity

    async with session_factory() as session:
        run = await _load_run(session)
        rows = (
            await session.execute(
                select(Opportunity)
                .where(Opportunity.source == SOURCE, Opportunity.key != RUN_KEY)
                .order_by(Opportunity.created_at.desc())
            )
        ).scalars().all()
    evidence = (run.evidence or {}) if run is not None else {}
    phase = (run.status if run is not None else "idle")
    return {
        "phase": phase if phase in ("searching", "done", "failed") else "idle",
        "message": evidence.get("message_ar") or "لم يبدأ البحث بعد.",
        "found": int(evidence.get("found") or 0),
        "errors": list(evidence.get("errors") or []),
        "external_contact": False,
        "opportunities": [_public_opportunity(row) for row in rows],
    }


async def _save_run(session_factory, *, status: str, message: str, found: int, errors: list[str]) -> None:
    from src.models import Opportunity

    now = datetime.now(UTC).isoformat()
    async with session_factory() as session:
        run = await _load_run(session)
        evidence = {
            "message_ar": message,
            "found": found,
            "errors": errors,
            "external_contact": False,
            "updated_at": now,
        }
        if run is None:
            run = Opportunity(
                key=RUN_KEY,
                title="بحث الرئيس التنفيذي عن الطلب المدفوع",
                description=message,
                area="growth",
                source=SOURCE,
                evidence=evidence,
                impact="مسودات فقط. لا يُرسل شيء للخارج.",
                confidence=1.0,
                priority=100,
                owner_agent="ceo",
                status=status,
            )
            session.add(run)
        else:
            run.status = status
            run.description = message
            run.evidence = {**(run.evidence or {}), **evidence}
        await session.commit()


async def _store_findings(session_factory, items: list[dict]) -> int:
    from src.models import Opportunity

    stored = 0
    async with session_factory() as session:
        for item in items:
            key = _key_for(item["url"])
            existing = (
                await session.execute(select(Opportunity).where(Opportunity.key == key))
            ).scalar_one_or_none()
            evidence = {
                "source_url": item["url"],
                "source_name": item["source_name"],
                "budget": item.get("budget"),
                "company": item.get("company"),
                "agent_label": item["agent_label"],
                "external_contact": False,
            }
            description = item["source_name"]
            if item.get("budget"):
                description += f" · {item['budget']}"
            if item.get("company"):
                description += f" · {item['company']}"
            if existing is None:
                session.add(Opportunity(
                    key=key,
                    title=item["title"],
                    description=description,
                    area="acquisition",
                    source=SOURCE,
                    evidence=evidence,
                    impact="طلب مدفوع منشور. مسودة بانتظار موافقة المالك. لا تواصل خارجي.",
                    confidence=0.8,
                    priority=80,
                    owner_agent=item["agent"],
                    status=AWAITING,
                ))
                stored += 1
            else:
                existing.evidence = {**(existing.evidence or {}), **evidence}
                existing.description = description
                existing.owner_agent = item["agent"]
                if existing.status not in ("approved", "rejected"):
                    existing.status = AWAITING
        await session.commit()
    return stored


async def start_search(session_factory, fetcher=None) -> dict:
    """Search public listings and store drafts. Never contacts the posters."""
    if _LOCK.locked():
        return await current_status(session_factory)
    fetch = fetcher or fetch_url
    async with _LOCK:
        await _save_run(
            session_factory,
            status="searching",
            message="الرئيس التنفيذي يبحث في الطلبات المنشورة…",
            found=0,
            errors=[],
        )
        items: list[dict] = []
        errors: list[str] = []
        for name, url, parser in (
            ("مستقل", MOSTAQL_URL, parse_mostaql),
            ("Remotive", REMOTIVE_URL, parse_remotive),
        ):
            try:
                body = await asyncio.to_thread(fetch, url)
                items.extend(parser(body))
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                logger.warning("CEO scout source %s failed: %s", name, type(exc).__name__)
                errors.append(name)
        await _store_findings(session_factory, items)
        if items:
            message = f"اكتمل البحث. {len(items)} فرصة بانتظار موافقتك. لم يُرسل شيء."
            status = "done"
        elif errors:
            message = "تعذّر الوصول إلى المصادر. لم تُخترع نتائج، ولم يُرسل شيء."
            status = "failed"
        else:
            message = "اكتمل البحث ولم تظهر طلبات مطابقة. لم يُرسل شيء."
            status = "done"
        await _save_run(session_factory, status=status, message=message, found=len(items), errors=errors)
        return await current_status(session_factory)


async def decide(session_factory, key: str, decision: str) -> dict | None:
    """Record approval or rejection. Does not create or send an outbound message."""
    from src.models import Opportunity

    if decision not in ("approve", "reject") or key == RUN_KEY or not key.startswith("scout-"):
        return None
    async with session_factory() as session:
        row = (
            await session.execute(
                select(Opportunity).where(Opportunity.key == key, Opportunity.source == SOURCE)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        row.status = "approved" if decision == "approve" else "rejected"
        evidence = dict(row.evidence or {})
        evidence["external_contact"] = False
        evidence["decided_at"] = datetime.now(UTC).isoformat()
        row.evidence = evidence
        await session.commit()
        await session.refresh(row)
        payload = _public_opportunity(row)
    payload["sent"] = False
    return payload
