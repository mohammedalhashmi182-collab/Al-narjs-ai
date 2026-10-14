# RAG eval (fixed set)

- `kbs/*.md`: four **fictional sample businesses** (clinic, salon, perfume store, restaurant). They are clearly
  labelled test data, are not real clients, and contain no real client names.
- `questions.json`: 208 questions, 52 per business. 32 are answerable (8 facts × 4 phrasings: MSA, Saudi dialect,
  short/colloquial, some English). 20 must be handed off (not in the KB, a request for a human, or a complaint).
  Regenerate with `python evals/rag/build_questions.py`.
- Runner: `python scripts/run_rag_eval.py [--mode mocked|live|auto] [--show-failures]`. Writes `evals/rag/results/<mode>.json`.

All four tenants share one database and every question goes through the real `tenant_reply.handle_inbound`, so
tenant isolation is tested on every question.

| metric | meaning |
|---|---|
| correct | answered, and every expected fact is in the reply |
| correct_handoff | handed off when the answer is not in the KB |
| missed | handed off although the KB had the answer (safe) |
| wrong | answered when it should hand off, or answered without the facts |
| hallucinations | a reply containing a number that is not in that tenant's KB |

Target (live): `(correct + correct_handoff) / total >= 0.90`, `wrong == 0`, `hallucinations == 0`.

Mocked mode = no model key: hash embeddings plus verbatim KB replies. This is exactly what production does without a
key. Its numbers are a floor, not the target. Note: retrieval (dialect map, weights, threshold) was tuned on this
same set, so a held-out set would give a fairer number.
