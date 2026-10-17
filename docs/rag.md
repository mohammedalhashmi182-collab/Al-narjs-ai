# RAG: tenant reply agent + site assistant

Code: `src/services/rag/` (arabic.py, embeddings.py, store.py, generate.py, site_kb.py).

1. **Index**: every `KnowledgeDoc` is split into FAQ-sized chunks and embedded (`agent_knowledge_chunks`,
   alembic 0011). Docs created/edited outside `add_doc` are (re)indexed lazily on the next query (content hash).
2. **Normalize**: أ/إ/آ→ا, ة→ه, ى→ي, tashkeel/tatweel removed, Arabic digits→ASCII, Saudi dialect words mapped
   (وش/ايش→ما, ابغى/ابي→اريد, دوام/اوقات→دوام, بكم→سعر, وين→موقع ...).
3. **Retrieve**: filtered by `project_id` first (NULL = Al-Narjis's own KB). pgvector `<=>` on Postgres when the
   extension exists (startup `ensure_pgvector` + migration 0011), else in-process cosine. Score = 0.5·cosine + 0.5·term coverage.
4. **Generate**: LLM in Saudi dialect, only from numbered sources; reply rejected if it has a number/link not in the
   sources or low lexical support → verbatim source snippet. `NO_ANSWER` or score < `RAG_MIN_CONFIDENCE` → human handoff
   (tenant: contact moved to the customer's human queue; site: "تحويل لخدمة العملاء" → ticket).
5. **Usage**: over the plan's monthly conversation limit no paid embedding/LLM call is made (`RAG_OVER_LIMIT`).

Embedding providers: `EMBEDDING_PROVIDER` (overrides `RAG_EMBED_PROVIDER`) = auto | openai | gemini | local | hash.
`auto` uses native Gemini embeddings when `GEMINI_API_KEY` is set. OpenAI is used only when the provider is
explicitly `openai`. A failed real provider is not answered with hash vectors.

`local` is opt-in (`EMBEDDING_PROVIDER=local`): `paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions, via
sentence-transformers. It is not the default and not a fallback. The production web service is Render's
starter plan (`render.yaml`, 512 MB RAM — [Render compute plans](https://render.com/docs/compute-plans)).
The model weights are about 470 MB and a CPU torch process needs more resident memory than that instance
has left, so loading it there would run the service out of memory. The package is not in the production
image. Use it only on a machine with several gigabytes free (a 4 GB plan is the practical floor) after
installing `sentence-transformers` there.

Chunks store the provider name in `model` and the width in `dim`. A change of either reindexes that
document and drops the previous provider's rows. A fixed `vector(N)` column is recreated when N does not
match (768 for Gemini, 384 for MiniLM, 1536 for OpenAI small).

Tests: `tests/test_rag*.py` (mocked; no network). Real Postgres+pgvector: `RAG_PG_TEST_URL=... pytest tests/test_rag_pgvector.py`.
