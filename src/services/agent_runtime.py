"""One production execution path for every Al-Narjis specialist agent."""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from src.core.model_provider import ModelRequest
from src.services.agent_profiles import profile_for, system_block

_PLACEHOLDER = re.compile(r"\{\{[^}]+\}\}|غير محدد\s*—\s*افترض", re.I)


@dataclass
class RuntimeResult:
    content: str
    model: str = ""
    tokens_used: int = 0
    latency_ms: int = 0
    structured_output: Any = None
    quality: dict[str, Any] = field(default_factory=dict)


def _category(agent_def: Any) -> str:
    value = getattr(agent_def, "category", "general")
    return str(getattr(value, "value", value) or "general")


def deterministic_issues(content: str) -> list[str]:
    text = (content or "").strip()
    issues: list[str] = []
    if len(text) < 80:
        issues.append("incomplete: answer is too short")
    if _PLACEHOLDER.search(text):
        issues.append("unresolved template/default placeholder")
    if text.count("```") % 2:
        issues.append("unclosed code block")
    return issues


def _json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    candidates = [raw]
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        candidates.append(m.group(0))
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return None


async def _complete(model_provider: Any, model_spec: str, request: ModelRequest):
    try:
        return await model_provider.complete(model_spec, request)
    except Exception:
        return await model_provider.complete_with_fallback("gemini", request)


async def _review(
    model_provider: Any,
    *,
    slug: str,
    profile: Any,
    original_task: str,
    original_system: str,
    evidence: str,
    draft: str,
    locale: str,
) -> dict[str, Any]:
    system = (
        "You are the Al-Narjis independent Quality Gate. Review a specialist deliverable before a paying client sees it. "
        "Return JSON only: {\"verdict\":\"PASS|RETURN\",\"issues\":[\"...\"]}. "
        "Check completeness, factual grounding, arithmetic and units, contradictions, language, actionability, "
        "and whether externally verifiable claims are supported by the supplied evidence. "
        "Do not invent facts. Do not rewrite the answer here."
    )
    prompt = (
        f"agent={slug}\nevidence_mode={profile.evidence_mode}\nlocale={locale}\n\n"
        f"ORIGINAL TASK:\n{original_task[:9000]}\n\n"
        f"ORIGINAL SYSTEM:\n{original_system[:5000]}\n\n"
        f"RUNTIME EVIDENCE:\n{evidence[:12000] or '[none]'}\n\n"
        f"DRAFT:\n{draft[:16000]}\n\nJSON:"
    )
    res = await model_provider.complete_with_fallback(
        "gemini",
        ModelRequest(prompt=prompt, system_prompt=system, temperature=0.05, max_tokens=800),
    )
    data = _json_object(getattr(res, "content", "") or "") or {}
    verdict = str(data.get("verdict") or "").upper()
    issues = [str(x)[:400] for x in (data.get("issues") or []) if str(x).strip()]
    if verdict not in ("PASS", "RETURN"):
        return {"verdict": "RETURN", "issues": ["quality reviewer returned invalid JSON/verdict"]}
    return {"verdict": verdict, "issues": issues}


async def execute(
    model_provider: Any,
    agent_def: Any,
    *,
    prompt: str,
    system_prompt: str = "",
    tool_context: str = "",
    locale: str = "ar",
    client_name: str = "",
    metadata: dict | None = None,
    top_p: float | None = None,
    timeout: float | None = None,
    quality_gate: bool = True,
) -> RuntimeResult:
    """Execute one agent with skills, evidence discipline, fallback and QA."""
    slug = str(agent_def.slug)
    category = _category(agent_def)
    profile = profile_for(slug, category)
    runtime_system = system_block(
        slug,
        category,
        locale=locale,
        client_name=client_name,
        has_evidence=bool(tool_context.strip()),
    )
    full_system = (system_prompt + runtime_system).strip()
    full_prompt = prompt + (tool_context or "")

    requested_temp = float((getattr(agent_def, "default_parameters", {}) or {}).get("temperature", 0.7))
    requested_tokens = int((getattr(agent_def, "default_parameters", {}) or {}).get("max_tokens", 2000))
    request = ModelRequest(
        prompt=full_prompt,
        system_prompt=full_system,
        temperature=min(requested_temp, profile.temperature_cap),
        max_tokens=max(requested_tokens, profile.min_tokens),
        top_p=top_p if top_p is not None else float((getattr(agent_def, "default_parameters", {}) or {}).get("top_p", 1.0)),
        metadata=metadata or {},
    )

    started = time.perf_counter()
    call = _complete(model_provider, str(agent_def.default_model), request)
    response = await asyncio.wait_for(call, timeout=timeout) if timeout else await call
    draft = (getattr(response, "content", "") or "").strip()
    if not draft:
        raise RuntimeError("agent returned empty content")

    issues = deterministic_issues(draft)
    review = {"verdict": "PASS", "issues": []}
    review_error = None
    if quality_gate and profile.quality_gate:
        try:
            review = await _review(
                model_provider,
                slug=slug,
                profile=profile,
                original_task=prompt,
                original_system=full_system,
                evidence=tool_context,
                draft=draft,
                locale=locale,
            )
        except Exception as exc:
            review_error = type(exc).__name__
            if profile.evidence_mode == "strict":
                review = {
                    "verdict": "RETURN",
                    "issues": list(issues) + ["strict quality review unavailable"],
                }
            else:
                review = {"verdict": "RETURN" if issues else "PASS", "issues": list(issues)}

    all_issues = list(dict.fromkeys(issues + list(review.get("issues") or [])))
    corrected = False
    final = draft

    if review.get("verdict") != "PASS" or issues:
        corrected = True
        correction_system = (
            full_system
            + "\n\nThe previous draft failed Al-Narjis Quality Gate. Correct it. "
              "Use only the original task and supplied runtime evidence. Do not invent missing facts."
        )
        correction_prompt = (
            f"ORIGINAL TASK:\n{prompt}\n\nRUNTIME EVIDENCE:\n{tool_context or '[none]'}\n\n"
            f"REJECTED DRAFT:\n{draft}\n\nDEFECTS:\n- "
            + "\n- ".join(all_issues or ["quality review requested correction"])
            + "\n\nReturn only the corrected final deliverable."
        )
        fix = await model_provider.complete_with_fallback(
            "gemini",
            ModelRequest(
                prompt=correction_prompt,
                system_prompt=correction_system,
                temperature=min(0.2, profile.temperature_cap),
                max_tokens=max(profile.min_tokens, 2600),
                metadata=metadata or {},
            ),
        )
        final = (getattr(fix, "content", "") or "").strip()
        remaining = deterministic_issues(final)
        if not final or remaining:
            raise RuntimeError("Al-Narjis Quality Gate rejected the corrected deliverable")
        if profile.evidence_mode == "strict" and quality_gate:
            try:
                second = await _review(
                    model_provider,
                    slug=slug,
                    profile=profile,
                    original_task=prompt,
                    original_system=full_system,
                    evidence=tool_context,
                    draft=final,
                    locale=locale,
                )
            except Exception as exc:
                raise RuntimeError("strict quality verification unavailable") from exc
            if second.get("verdict") != "PASS":
                raise RuntimeError("strict evidence answer failed final Quality Gate")

    latency = int((time.perf_counter() - started) * 1000)
    structured = getattr(response, "structured_output", None)
    if hasattr(structured, "model_dump"):
        structured = structured.model_dump()
    return RuntimeResult(
        content=final,
        model=str(getattr(response, "model", "") or agent_def.default_model),
        tokens_used=int(getattr(response, "tokens_used", 0) or 0),
        latency_ms=latency,
        structured_output=structured,
        quality={
            "passed": True,
            "corrected": corrected,
            "evidence_mode": profile.evidence_mode,
            "skills": list(profile.skills),
            "tools": list(profile.tools),
            "review_error": review_error,
        },
    )
