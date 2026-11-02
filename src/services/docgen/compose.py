"""Narrative composition. The model may only phrase facts; it may not add figures.

A draft whose numbers are not in the fact list is rejected and requested once
more. A second miss is dropped and replaced by a deterministic Arabic text
built only from those facts.
"""

from __future__ import annotations

import asyncio
import json
import re

from src.services.docgen.guard import offending_numbers
from src.services.docgen.schema import Analysis, Narrative

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)

_SYSTEM = (
    "You write the narrative for an Arabic-first Saudi B2B document. "
    "Return one JSON object and nothing else, with keys headline_ar, summary_ar, "
    "insights_ar, recommendations_ar, headline_en, summary_en. "
    "insights_ar and recommendations_ar are arrays of at most three short strings. "
    "Every number you write must be copied from ALLOWED_NUMBERS. Do not calculate, "
    "round to a new value, estimate a market, or invent a date, percentage, count, "
    "or currency figure. If a figure is not in the list, leave it out. "
    "Do not use numbered lists. Arabic is the primary language."
)

_NO_DIGIT = Narrative(
    headline_ar="ملخص البيانات",
    summary_ar="وُضعت الأرقام المحسوبة في الجدول. هذا النص لا يضيف رقماً من عنده.",
    insights_ar=[
        "الأرقام الظاهرة محسوبة من البيانات المرفوعة أو من الأرقام المكتوبة في الطلب.",
        "ملف إكسل يحتوي صيغاً للمجاميع والمتوسطات.",
        "العرض التقديمي يعرض نفس الأرقام المحسوبة.",
    ],
    recommendations_ar=[
        "راجع الجدول قبل أي قرار.",
        "حدّث البيانات ثم أعد توليد الحزمة حتى تبقى الصيغ هي مصدر الرقم.",
        "لا تعتمد رقماً غير موجود في الجدول.",
    ],
    headline_en="Data summary",
    summary_en="The computed figures are in the table. This text adds none of its own.",
    source="deterministic",
)


def deterministic_narrative(analysis: Analysis, *, source: str = "deterministic") -> Narrative:
    """Arabic (and a short English line) interpolated only from fact displays."""
    lines_ar: list[str] = []
    lines_en: list[str] = []
    for fact in analysis.facts_of("count"):
        if fact.key in {"row_count", "column_count"}:
            lines_ar.append(f"{fact.label_ar}: {fact.display}.")
            lines_en.append(f"{fact.label_en}: {fact.display}.")
    for fact in analysis.facts_of("total"):
        lines_ar.append(f"{fact.label_ar}: {fact.display}.")
        lines_en.append(f"{fact.label_en}: {fact.display}.")
    for fact in analysis.facts_of("average"):
        if analysis.primary_metric and fact.key == f"average:{analysis.primary_metric}":
            lines_ar.append(f"{fact.label_ar}: {fact.display}.")
            lines_en.append(f"{fact.label_en}: {fact.display}.")
    growth = analysis.facts_of("growth")
    if growth:
        lines_ar.append(f"{growth[0].label_ar}: {growth[0].display}.")
        lines_en.append(f"{growth[0].label_en}: {growth[0].display}.")
    forecast = analysis.facts_of("forecast")
    if forecast:
        lines_ar.append(f"{forecast[0].label_ar}: {forecast[0].display}.")
        lines_en.append(f"{forecast[0].label_en}: {forecast[0].display}.")
    for note in analysis.notes_ar:
        if not any(character.isdigit() for character in note):
            lines_ar.append(note)
    if not lines_ar:
        narrative = Narrative(
            headline_ar=_NO_DIGIT.headline_ar,
            summary_ar=_NO_DIGIT.summary_ar,
            insights_ar=list(_NO_DIGIT.insights_ar),
            recommendations_ar=list(_NO_DIGIT.recommendations_ar),
            headline_en=_NO_DIGIT.headline_en,
            summary_en=_NO_DIGIT.summary_en,
            source=source,
        )
    else:
        headline_fact = next((fact for fact in analysis.facts_of("total") if analysis.primary_metric and fact.key.endswith(analysis.primary_metric)), None)
        headline_ar = (
            f"{headline_fact.label_ar} {headline_fact.display}"
            if headline_fact
            else "ملخص الأرقام المحسوبة"
        )
        headline_en = (
            f"{headline_fact.label_en} {headline_fact.display}"
            if headline_fact
            else "Computed figures"
        )
        narrative = Narrative(
            headline_ar=headline_ar,
            summary_ar=" ".join(lines_ar),
            insights_ar=lines_ar[:3],
            recommendations_ar=list(_NO_DIGIT.recommendations_ar),
            headline_en=headline_en,
            summary_en=" ".join(lines_en),
            source=source,
        )
    if offending_numbers(narrative.full_text(), analysis.allowed_values()):
        fallback = Narrative(
            headline_ar=_NO_DIGIT.headline_ar,
            summary_ar=_NO_DIGIT.summary_ar,
            insights_ar=list(_NO_DIGIT.insights_ar),
            recommendations_ar=list(_NO_DIGIT.recommendations_ar),
            headline_en=_NO_DIGIT.headline_en,
            summary_en=_NO_DIGIT.summary_en,
            source=source,
        )
        return fallback
    return narrative


async def compose_narrative(analysis: Analysis, *, brief: str, model_provider=None) -> Narrative:
    if model_provider is None:
        return deterministic_narrative(analysis)
    allowed = analysis.allowed_values()
    prompt = _prompt(analysis, brief, rejected=None)
    draft = await _ask(model_provider, prompt)
    narrative = _parse(draft) if draft else None
    if narrative is not None and not offending_numbers(narrative.full_text(), allowed):
        narrative.source = "model"
        return narrative
    rejected = offending_numbers(narrative.full_text(), allowed) if narrative else []
    second = await _ask(model_provider, _prompt(analysis, brief, rejected=rejected or [-1]))
    narrative = _parse(second) if second else None
    if narrative is not None and not offending_numbers(narrative.full_text(), allowed):
        narrative.source = "model"
        return narrative
    dropped = deterministic_narrative(analysis, source="dropped")
    bad = offending_numbers((second or draft or ""), allowed)
    dropped.rejected_numbers = [str(number) for number in (bad or rejected)]
    return dropped


def _prompt(analysis: Analysis, brief: str, rejected: list[float] | None) -> str:
    catalog = [
        {"label_ar": fact.label_ar, "label_en": fact.label_en, "value": fact.display, "kind": fact.kind}
        for fact in analysis.facts
        if fact.kind != "source"
    ]
    allowed = sorted({fact.display for fact in analysis.facts})
    warning = ""
    if rejected:
        shown = ", ".join(str(number) for number in rejected[:12])
        warning = (
            "The previous draft was rejected because it used numbers that are not allowed: "
            f"{shown}. Rewrite the JSON without those numbers and without any number that is "
            "not copied from ALLOWED_NUMBERS.\n"
        )
    return (
        f"{warning}"
        f"BRIEF (context only; do not add its numbers unless they are in ALLOWED_NUMBERS):\n{(brief or '')[:2000]}\n\n"
        f"FACTS:\n{json.dumps(catalog, ensure_ascii=False)}\n\n"
        f"ALLOWED_NUMBERS:\n{json.dumps(allowed, ensure_ascii=False)}\n"
    )


async def _ask(provider, prompt: str) -> str:
    try:
        from src.core.model_provider import ModelRequest

        request = ModelRequest(
            prompt=prompt,
            system_prompt=_SYSTEM,
            temperature=0.2,
            max_tokens=900,
        )
        call = _dispatch(provider, request)
        response = await asyncio.wait_for(call, timeout=20)
    except Exception:
        return ""
    return str(getattr(response, "content", "") or "")


async def _dispatch(provider, request):
    if callable(getattr(provider, "complete_with_fallback", None)):
        return await provider.complete_with_fallback("gemini", request)
    return await provider.complete(request)


def _parse(raw: str) -> Narrative | None:
    text = _FENCE.sub("", (raw or "").strip())
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    headline = str(data.get("headline_ar") or "").strip()[:300]
    summary = str(data.get("summary_ar") or "").strip()[:2000]
    if not headline and not summary:
        return None
    return Narrative(
        headline_ar=headline or "ملخص",
        summary_ar=summary,
        insights_ar=_as_list(data.get("insights_ar")),
        recommendations_ar=_as_list(data.get("recommendations_ar")),
        headline_en=str(data.get("headline_en") or "").strip()[:300],
        summary_en=str(data.get("summary_en") or "").strip()[:2000],
        source="model",
    )


def _as_list(value) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = [str(item) for item in value]
    else:
        items = []
    return [item.strip()[:400] for item in items if item and str(item).strip()][:3]
