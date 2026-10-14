"""RAG eval runner.

  python scripts/run_rag_eval.py                 # mocked (deterministic, no network) – CI
  python scripts/run_rag_eval.py --mode live     # real embeddings + LLM; needs a model key in env
  python scripts/run_rag_eval.py --mode auto     # live if a key exists, else mocked

Writes evals/rag/results/<mode>.json. Exit 1 when the target is missed
(>= 90% correct-or-correct-handoff, 0 wrong, 0 hallucinations).
Never prints key values; only key NAMES that are present.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SECRET_KEY", "eval-only-not-a-secret")
os.environ.setdefault("OWNER_PASSWORD", "eval-only-not-a-secret")
os.environ.setdefault("ENVIRONMENT", "test")
# the app engine is never used (the eval runs on its own in-memory DB); this only satisfies settings
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./rag_eval_unused.db")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["mocked", "live", "auto"], default="mocked")
    ap.add_argument("--show-failures", action="store_true")
    args = ap.parse_args()

    from src.services.rag import evaluate

    keys = evaluate.available_live_keys()
    mode = args.mode
    if mode == "auto":
        mode = "live" if keys else "mocked"
    if mode == "live" and not keys:
        print("live eval skipped: no model key in env (checked: " + ", ".join(evaluate.LIVE_KEYS) + ")")
        return 0
    if mode == "live":
        os.environ.setdefault("RAG_EMBED_PROVIDER", "auto")
        print("live eval with keys present: " + ", ".join(keys))
    rep = asyncio.run(evaluate.run(mode))
    s = rep.summary()
    out = evaluate.ROOT / "results"
    out.mkdir(exist_ok=True)
    (out / f"{mode}.json").write_text(json.dumps({**s, "failures": rep.failures}, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    print(json.dumps({k: v for k, v in s.items() if k != "by_business"}, ensure_ascii=False, indent=1))
    if args.show_failures:
        for f in rep.failures:
            print(f["outcome"], f["id"], f["q"], "|", (f["meta"] or {}).get("confidence"), "|", (f["reply"] or "")[:90].replace("\n", " "))
    return 0 if s["target_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
