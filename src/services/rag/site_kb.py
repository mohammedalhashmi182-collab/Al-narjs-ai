"""Al-Narjis's own product facts for the site assistant, generated from
``catalog`` at runtime (single source of truth: a price change in the catalog
changes the assistant's sources too, lesson 3). No number is written here.

Retrieved together with the owner KB docs (``project_id`` NULL). Never
includes any tenant data. Vectors are cached per (embedder, text).
"""

from __future__ import annotations

from src.core.pii_mask import for_embedding

from . import embeddings
from .arabic import terms
from .store import LEX_W, VEC_W, coverage

_CACHE: dict[tuple[str, str], list[float]] = {}


def docs() -> list[tuple[str, str]]:
    from src.services import catalog

    out: list[tuple[str, str]] = []
    for key in catalog.PACKAGE_ORDER:
        p = catalog.PACKAGES[key]
        setup = int(p.get("setup_fee") or 0) // 100
        out.append((f"باقة {p['name']} ({p['name_en']})",
                    f"سعر باقة {p['name']} ({p['name_en']} plan): {p['price']} ريال شهريًا قبل ضريبة القيمة المضافة. "
                    f"رسوم الإعداد: {setup} ريال. عدد الوكلاء: {p.get('agents', '')}.\n"
                    + "\n".join(p.get("scope", []))))
    e = catalog.ENTERPRISE
    out.append(("باقة المؤسسات (Enterprise)", "\n".join([e["tagline"], *e["scope"]])))
    a = catalog.ADDON_AGENT
    out.append(("وكيل إضافي", f"{a['name']}: {a['price']} ريال شهريًا لكل وكيل، بحد أقصى {catalog.MAX_ADDON_AGENTS} وكيلًا."))
    c = catalog.USAGE_ADDONS["conversations"]
    out.append(("حزم المحادثات", f"حزمة {c['name']}: {c['price']} ريال. {c['note']}"))
    out.append(("ضمان الإعداد والاسترداد", catalog.SETUP_GUARANTEE["text"]))
    return out


async def retrieve(query: str, embedder: embeddings.Embedder | None = None, k: int = 3) -> list[dict]:
    embedder = embedder or embeddings.get_embedder()
    items = docs()
    texts = [f"{t}\n{b}" for t, b in items]
    embed_query = for_embedding(query)
    embedder, (qv,) = await embeddings.embed_safe(embedder, [embed_query], kind="query")
    missing = [x for x in texts if (embedder.name, x) not in _CACHE]
    if missing:
        used, vecs = await embeddings.embed_safe(embedder, missing, kind="doc")
        if used.name == embedder.name:
            for x, v in zip(missing, vecs, strict=True):
                _CACHE[(embedder.name, x)] = v
        else:  # provider failed mid-way: hash for both sides
            embedder = used
            (qv,) = await used.embed([embed_query], kind="query")
            for x, v in zip(missing, vecs, strict=True):
                _CACHE[(used.name, x)] = v
    q_terms = terms(query)
    hits = []
    for (title, body), x in zip(items, texts, strict=True):
        v = _CACHE.get((embedder.name, x)) or (await embedder.embed([x]))[0]
        cos = embeddings.cosine(qv, v)
        cov = coverage(q_terms, x)
        hits.append({"title": title, "text": body, "score": round(VEC_W * max(0.0, cos) + LEX_W * cov, 4),
                     "cosine": round(cos, 4), "coverage": round(cov, 4)})
    hits.sort(key=lambda h: -h["score"])
    return hits[:k]
