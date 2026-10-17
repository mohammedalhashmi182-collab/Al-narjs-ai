"""Second-model review of deep answers: accuracy vs sources, correct Arabic, no unsupported claims."""

from __future__ import annotations

import json
import re

REVIEW_SYSTEM = (
    "أنت مراجع جودة لردود شركة النرجس. قيّم الرد مقابل المصادر فقط: "
    "1) دقيق ومطابق للمصادر 2) عربي سليم 3) لا يحتوي أسعار أو عروض أو أرقام أو وعود غير موجودة في المصادر. "
    'أعد JSON فقط: {"ok": true|false, "reason": "..."}'
)


def parse_verdict(raw: str) -> tuple[bool, str]:
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return False, "unparseable review"
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return False, "unparseable review"
    return bool(data.get("ok") is True), str(data.get("reason", ""))


async def review(reviewer, question: str, answer: str, context: str) -> tuple[bool, str]:
    """``reviewer`` is any object with ``async chat(system, user)``. Fails closed."""
    user = f"المصادر:\n{context}\n\nسؤال العميل:\n{question}\n\nالرد المقترح:\n{answer}"
    try:
        raw = await reviewer.chat(REVIEW_SYSTEM, user)
    except Exception:
        return False, "review unavailable"
    return parse_verdict(raw)
