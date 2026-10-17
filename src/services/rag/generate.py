"""Grounded answer generation (Saudi dialect) with confidence-based handoff.

``answer(question, hits, ...)`` returns an ``Answer`` whose ``handoff`` reason is
set whenever the bot must not answer on its own:

* ``low_confidence``  best retrieved chunk below ``store.min_confidence()``
* ``no_answer``       the LLM said the sources do not answer the question
* ``ungrounded``      LLM reply had a number/link not in the sources and no
                      safe extractive fallback was possible

The LLM (seam ``_llm_complete``) writes in a warm Saudi dialect and is told to
use ONLY the numbered sources. Its reply is rejected (→ verbatim source
snippet, or handoff) if it is empty, too long, contains a number or link that
is not in the sources, or is not lexically supported by them. With no model
key, the reply is the verbatim best snippet (never invented text).

Based on ``fix/tenant-reply-llm`` (grounded() / NO_ANSWER contract), extended
with retrieval confidence, dialect prompt and lexical support check.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass, field

from .arabic import light_stem, terms

log = logging.getLogger(__name__)

NO_ANSWER = "NO_ANSWER"
MAX_CHARS = 900
LLM_TIMEOUT = float(os.getenv("RAG_LLM_TIMEOUT", "15"))
MIN_SUPPORT = float(os.getenv("RAG_MIN_SUPPORT", "0.5"))

SYSTEM_AR = (
    "أنت موظف خدمة عملاء لدى {name}، ترد على العملاء باللهجة السعودية البيضاء بأسلوب ودود ومختصر (جملتين إلى أربع). "
    "أجب فقط من المصادر المرقمة المرفقة. ممنوع تضيف أي معلومة أو سعر أو رقم أو موعد أو رابط أو عرض أو خصم غير مكتوب حرفيًا في المصادر. "
    "انقل الأرقام والأسعار كما هي بالضبط. لا تذكر أنك ذكاء اصطناعي ولا تذكر أي شركة أخرى. "
    "إذا المصادر ما تجاوب على السؤال بشكل واضح وكامل فاكتب فقط: " + NO_ANSWER
)

_NUM = re.compile(r"\d+(?:[.,]\d+)?")
_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٬٫", "0123456789,.")
# Words the dialect reply may add without being "facts".
_FILLER = frozenset(terms(
    "اهلا هلا حياك الله ابشر اكيد طبعا تقدر تقدرين نقدر نتشرف نسعد بخدمتك بخدمتكم يسعدنا اي استفسار ثاني حاضرين "
    "موجودين عندنا لدينا بس فقط تحت امرك امرك نعم لا ايه ايوه يعطيك العافيه حبيبي عزيزي عزيزتي غاليه غالي اخوي اختي "
    "ريال ساعه دوام يوم ايام دقيقه دقايق الساعه صباحا مساء الصبح العصر الليل الظهر"))


@dataclass
class Answer:
    text: str | None
    source: str  # llm | extractive | handoff
    confidence: float
    handoff: str | None = None
    sources: list[str] = field(default_factory=list)
    latency_ms: int = 0


async def _llm_complete(system: str, prompt: str) -> str | None:
    """One LLM call through the app's fallback chain (seam for tests). None when no key / error."""
    from src.config.settings import get_settings

    st = get_settings()
    if not any(getattr(st, k, None) for k in ("gemini_api_key", "moonshot_api_key", "openrouter_api_key",
                                               "openai_api_key", "groq_api_key", "anthropic_api_key")):
        return None
    try:
        from src.core.model_provider import ModelProvider, ModelRequest

        req = ModelRequest(prompt=prompt, system_prompt=system, temperature=0.1, max_tokens=400)
        res = await asyncio.wait_for(ModelProvider(st).complete_with_fallback("gemini", req), LLM_TIMEOUT)
        return (res.content or "").strip() or None
    except Exception as exc:  # noqa: BLE001
        log.warning("RAG LLM call failed: %s", type(exc).__name__)
        return None


def _links(text: str) -> set[str]:
    """Exact link strings. A shorter prefix of a source URL is a different link."""
    return {u.rstrip(".,)") for u in _URL.findall(text or "")}


def grounded(reply: str, hits: list[dict], extra_facts: str = "") -> bool:
    """Every number and link in the reply appears in the sources.

    Links match exactly. ``https://karmaai.online`` does not count as the
    source link ``https://karmaai.online/docs/terms.pdf``.
    """
    source = (" ".join(str(h.get("text") or "") + " " + str(h.get("title") or "") for h in hits) + " " + extra_facts)
    source = source.translate(_AR_DIGITS)
    out = (reply or "").translate(_AR_DIGITS)
    src_nums = {n.replace(",", "") for n in _NUM.findall(source)}
    if any(n.replace(",", "") not in src_nums for n in _NUM.findall(out)):
        return False
    src_links = _links(source)
    return all(u.rstrip(".,)") in src_links for u in _URL.findall(out))


def support(reply: str, hits: list[dict]) -> float:
    """Share of the reply's content terms that occur in the sources (fillers ignored)."""
    src = {light_stem(t) for h in hits for t in terms(f"{h.get('title', '')} {h.get('text', '')}")}
    words = [light_stem(t) for t in terms(reply) if t not in _FILLER and not t.isdigit()]
    if not words:
        return 1.0
    return sum(1 for w in words if w in src) / len(words)


def extractive(hits: list[dict]) -> str:
    from src.ai.sanitize import sanitize_public_text

    top = sanitize_public_text(str(hits[0]["text"]))
    if len(top) > 700:
        top = top[:700].rsplit(" ", 1)[0] + "…"
    return f"أهلًا بك 🌿\n{top}\n\nإذا عندك سؤال ثاني أنا حاضر."


def build_prompt(question: str, hits: list[dict]) -> str:
    src = "\n\n".join(f"[{i + 1}] {h.get('title') or ''}\n{str(h.get('text') or '')[:1500]}" for i, h in enumerate(hits))
    return f"المصادر:\n{src}\n\nسؤال العميل:\n{question[:1000]}\n\nالرد:"


async def answer(question: str, hits: list[dict], *, name: str = "", allow_llm: bool = True,
                 min_confidence: float | None = None, guard=None) -> Answer:
    from .store import min_confidence as _minc

    t0 = time.perf_counter()
    thr = _minc() if min_confidence is None else min_confidence
    conf = float(hits[0]["score"]) if hits else 0.0
    titles = [str(h.get("title") or "") for h in hits]

    def done(a: Answer) -> Answer:
        a.latency_ms = int((time.perf_counter() - t0) * 1000)
        return a

    if not hits or conf < thr:
        return done(Answer(None, "handoff", conf, "low_confidence", titles))
    # Only sources reasonably close to the best one go to the model.
    used = [h for h in hits if float(h["score"]) >= max(thr, conf - 0.25)] or hits[:1]
    fallback = extractive(used)
    reply = await _llm_complete(SYSTEM_AR.format(name=name or "المتجر"), build_prompt(question, used)) if allow_llm else None
    if reply is None:
        return done(Answer(fallback, "extractive", conf, None, titles))
    if NO_ANSWER in reply.upper():
        return done(Answer(None, "handoff", conf, "no_answer", titles))
    from src.ai.sanitize import sanitize_public_text

    reply = sanitize_public_text(reply)
    bad = (not reply or len(reply) > MAX_CHARS or not grounded(reply, used) or support(reply, used) < MIN_SUPPORT
           or (guard is not None and guard(reply)))
    if bad:
        log.info("RAG reply rejected (ungrounded); using the verbatim source")
        return done(Answer(fallback, "extractive", conf, None, titles))
    return done(Answer(reply, "llm", conf, None, titles))

