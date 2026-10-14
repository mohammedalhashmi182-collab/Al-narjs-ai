"""Run the agent evals (mocked model) and print before/after per agent.

    python scripts/run_agent_evals.py [--json]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SECRET_KEY", "eval-only")
os.environ.setdefault("OWNER_PASSWORD", "eval-only")

from src.services import agent_evals  # noqa: E402

before, after = agent_evals.run(False), agent_evals.run(True)
if "--json" in sys.argv:
    print(json.dumps({"before": before, "after": after}, ensure_ascii=False, indent=1))
else:
    print(f"{'agent':24} before  after")
    for slug in before:
        print(f"{slug:24} {before[slug]:6.1f} {after[slug]:6.1f}")
    n = len(before)
    print(f"{'MEAN':24} {sum(before.values())/n:6.1f} {sum(after.values())/n:6.1f}")
