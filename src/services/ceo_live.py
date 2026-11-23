"""Live team run: the AI CEO assigns real work to up to four agents in front of the visitor.

Every agent step is a real model call. If no model is configured, the run is
refused as ``unavailable`` and no agent is shown as working. Nothing here
invents metrics: the run returns only what the model produced.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from src.core.model_provider import ModelRequest
from src.services import catalog, ceo_advisor, saas_offer

MAX_AGENTS = 4
AGENT_TOKENS = 350
FINAL_TOKENS = 600
STEP_TIMEOUT_SECONDS = 25


def select_agents(problem: str) -> list[str]:
    """Pick up to MAX_AGENTS real catalog agents for the problem, in rule order."""
    diagnosis = ceo_advisor.diagnose_rules(problem)
    chosen: list[str] = []
    for slug in diagnosis.agents:
        if slug in catalog.EMPLOYEES and slug not in chosen:
            chosen.append(slug)
        if len(chosen) == MAX_AGENTS:
            break
    return chosen


def _agent_name(slug: str, lang: str = "ar") -> str:
    """Display title from the catalog. Catalog agents carry title_ar/title_en, not name."""
    info = catalog.EMPLOYEES.get(slug, {}) or {}
    key = "title_en" if lang == "en" else "title_ar"
    return str(info.get(key) or info.get("title_ar") or slug)


def _model_ready(provider: Any) -> bool:
    return provider is not None and ceo_advisor._has_cloud_model(provider)


async def _ask(provider: Any, system: str, prompt: str, max_tokens: int) -> str:
    response = await asyncio.wait_for(
        provider.complete_with_fallback(
            "gemini", ModelRequest(prompt=prompt, system_prompt=system, max_tokens=max_tokens)
        ),
        timeout=STEP_TIMEOUT_SECONDS,
    )
    return saas_offer.clean_multiline(getattr(response, "content", ""))


def _agent_system(name: str, lang: str) -> str:
    if lang == "en":
        return (
            f"You are the {name} agent on the Al-Narjis AI team. Do only your part of the "
            "request. Answer in at most three short bullet points. Do not quote prices, "
            "numbers or results you cannot verify."
        )
    return (
        f"أنت وكيل {name} في فريق النرجس للذكاء الاصطناعي. نفّذ جزءك فقط من الطلب، "
        "في ثلاث نقاط قصيرة كحد أقصى. لا تذكر أسعاراً أو أرقاماً أو نتائج لا يمكن التحقق منها."
    )


def _final_system(lang: str) -> str:
    if lang == "en":
        return (
            "You are the AI CEO of Al-Narjis AI. Combine the agents' work into one clear answer "
            "for the visitor, with the next step. Do not invent prices or results."
        )
    return (
        "أنت الرئيس التنفيذي للنرجس للذكاء الاصطناعي. ادمج عمل الوكلاء في جواب واحد واضح "
        "للزائر مع الخطوة التالية. لا تخترع أسعاراً ولا نتائج."
    )


async def run_team(problem: str, *, provider: Any, lang: str = "ar") -> AsyncIterator[dict]:
    """Yield run events: team, agent_start, agent_done, final, or unavailable."""
    try:
        text = ceo_advisor.validate_problem(problem)
    except ValueError:
        yield {"type": "error", "message": "problem too short"}
        return

    if not _model_ready(provider):
        yield {"type": "unavailable"}
        return

    slugs = select_agents(text)
    if not slugs:
        yield {"type": "no_agents"}
        return

    yield {"type": "team", "agents": [{"slug": s, "name": _agent_name(s, lang)} for s in slugs]}

    outputs: list[tuple[str, str]] = []
    for slug in slugs:
        name = _agent_name(slug, lang)
        yield {"type": "agent_start", "slug": slug, "name": name}
        try:
            answer = await _ask(provider, _agent_system(name, lang), text, AGENT_TOKENS)
        except Exception:  # noqa: BLE001 - one agent failing must not hide the others
            answer = ""
        if answer:
            outputs.append((name, answer))
        yield {"type": "agent_done", "slug": slug, "name": name, "text": answer}

    if not outputs:
        yield {"type": "unavailable"}
        return

    brief = "\n\n".join(f"{name}:\n{answer}" for name, answer in outputs)
    prompt = f"طلب الزائر:\n{text}\n\nعمل الوكلاء:\n{brief}" if lang != "en" else (
        f"Visitor request:\n{text}\n\nAgent work:\n{brief}"
    )
    try:
        final = await _ask(provider, _final_system(lang), prompt, FINAL_TOKENS)
    except Exception:  # noqa: BLE001
        final = ""
    if not final:
        yield {"type": "unavailable"}
        return
    yield {"type": "final", "text": final}


def sse_line(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
