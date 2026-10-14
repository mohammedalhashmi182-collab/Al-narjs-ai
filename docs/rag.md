# RAG: tenant reply agent + site assistant

Code: `src/services/rag/` (arabic.py, embeddings.py, store.py, generate.py, site_kb.py).

1. **Index**: every `KnowledgeDoc` is split into FAQ-sized chunks and embedded (`agent_knowledge_chunks`,
   alembic 0010). Docs created/edited outside `add_doc` are (re)indexed lazily on the next query (content hash).
2. **Normalize**: أ/إ/آ→ا, ة→ه, ى→ي, tashkeel/tatweel removed, Arabic digits→ASCII, Saudi dialect words mapped
   (وش/ايش→ما, ابغى/ابي→اريد, دوام/اوقات→دوام, بكم→سعر, وين→موقع ...).
3. **Retrieve**: filtered by `project_id` first (NULL = Al-Narjis's own KB). pgvector `<=>` on Postgres when the
   extension exists (startup `ensure_pgvector` + migration 0010), else in-process cosine. Score = 0.5·cosine + 0.5·term coverage.
4. **Generate**: LLM in Saudi dialect, only from numbered sources; reply rejected if it has a number/link not in the
   sources or low lexical support → verbatim source snippet. `NO_ANSWER` or score < `RAG_MIN_CONFIDENCE` → human handoff
   (tenant: contact moved to the customer's human queue; site: "تحويل لخدمة العملاء" → ticket).
5. **Usage**: over the plan's monthly conversation limit no paid embedding/LLM call is made (`RAG_OVER_LIMIT`).

Embedding providers: `RAG_EMBED_PROVIDER` = auto | openai | gemini | local | hash. `local` needs the optional
`sentence-transformers` package (not installed by default: large download).

Tests: `tests/test_rag*.py` (mocked; no network). Real Postgres+pgvector: `RAG_PG_TEST_URL=... pytest tests/test_rag_pgvector.py`.
