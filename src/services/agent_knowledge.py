"""Curated knowledge packs for the specialist agents.

"Training" here means grounding, not fine-tuning: each agent gets a pack in
``knowledge/agents/<slug>.json`` (role prompt, guardrails, playbooks, sourced
domain facts, a few-shot example). At run time the most relevant facts are
retrieved with the same token-overlap search the customer knowledge base uses
and injected into the prompt. Packs are distilled in our own words from public
sources listed in ``knowledge/agents/_shared.json``; nothing here is sent
anywhere. Missing/invalid packs degrade to an empty block, never an error.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PACK_DIR = Path(__file__).resolve().parents[2] / "knowledge" / "agents"
MARKER = "[حزمة المعرفة"


@lru_cache(maxsize=1)
def shared() -> dict:
    try:
        return json.loads((PACK_DIR / "_shared.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"sources": {}, "facts": []}


@lru_cache(maxsize=64)
def load_pack(slug: str) -> dict | None:
    if not slug or "/" in slug or slug.startswith("_"):
        return None
    path = PACK_DIR / f"{slug}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return data if data.get("slug") == slug else None


def pack_slugs() -> list[str]:
    return sorted(p.stem for p in PACK_DIR.glob("*.json") if not p.stem.startswith("_"))


def sources_for(pack: dict) -> list[dict]:
    reg = shared().get("sources", {})
    return [{"key": k, **reg[k]} for k in pack.get("sources", []) if k in reg]


def relevant_facts(slug: str, query: str, k: int = 6) -> list[dict]:
    pack = load_pack(slug)
    if not pack:
        return []
    from src.services.agent_tools import knowledge_base

    facts = list(pack.get("facts", [])) + list(shared().get("facts", []))
    by_id = {f["id"]: f for f in facts}
    hits = knowledge_base.search_texts([(f["id"], f["text"]) for f in facts], query or "", k=k) if query else []
    chosen, seen = [], set()
    for h in hits:
        if h["title"] not in seen:
            seen.add(h["title"])
            chosen.append(by_id[h["title"]])
    # Always keep the agent's core facts in view when retrieval is thin.
    for f in pack.get("facts", []):
        if len(chosen) >= max(3, min(k, len(hits) + 3)):
            break
        if f["id"] not in seen:
            seen.add(f["id"])
            chosen.append(f)
    return chosen[:k]


def expert_block(slug: str, query: str = "", k: int = 6) -> str:
    """Prompt section with the agent's pack. Empty string if no pack."""
    pack = load_pack(slug)
    if not pack:
        return ""
    lines = [f"\n\n{MARKER}: {slug} v{pack.get('version', 1)} — {pack.get('specialty', '')}]",
             pack.get("system_prompt", "")]
    guard = list(pack.get("guardrails", [])) + [
        "لا تخترع أرقاماً أو عملاء أو شهادات، ولا تعرض خصماً لم يحدده صاحب النشاط؛ اذكر افتراضاتك."]
    lines.append("قواعد ملزمة: " + "؛ ".join(guard))
    for pb in pack.get("playbooks", [])[:2]:
        lines.append(f"منهجية «{pb['name']}»: " + " ← ".join(pb.get("steps", [])))
    facts = relevant_facts(slug, query, k)
    if facts:
        lines.append("معرفة متخصصة موثّقة (استخدمها ولا تتجاوزها):")
        lines += [f"• {f['text']}" for f in facts]
    for ex in pack.get("few_shot", [])[:1]:
        lines.append(f"مثال — المدخل: {ex['input']}\nمثال — المخرج المتوقع: {ex['output']}")
    src = [s["title"] for s in sources_for(pack)][:8]
    if src:
        lines.append("المراجع: " + "، ".join(src))
    return "\n".join(x for x in lines if x)
