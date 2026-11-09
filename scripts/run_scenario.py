"""Run the six-event scenario: KB-grounded agents, then the plain-LLM baseline.   python scripts/run_scenario.py [--baseline-only|--grounded-only]

Needs: the built KB (scripts/build_kb.py), the local embedding model, OPENAI_API_KEY in .env. All model calls go through
agents.llm.call_llm (disk-cached by input hash, token-logged to audit/llm_usage.jsonl). Output: audit/runs/<run_id>.jsonl
(grounded), <run_id>.baseline.jsonl, and a small manifest. Nothing is final until a human approves it:
  python -m agents.approvals list <run_id>
"""
from __future__ import annotations

import json
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.llm import CONFIG, call_llm  # noqa: E402
from kb.embedder import get_embedder  # noqa: E402
from kb.retrieval import Retriever  # noqa: E402
from scenario.engine import load_scenario, make_run_id, run_baseline, run_grounded  # noqa: E402


def verbose_llm(*args, **kw):
    """call_llm with a progress line per call (the run makes ~120 calls and each can take tens of seconds)."""
    t0 = time.time()
    r = call_llm(*args, **kw)
    print(f"  [{time.strftime('%H:%M:%S')}] {kw.get('purpose', '?'):<34} {'cached' if r.cached else f'{time.time() - t0:5.1f}s'}  "
          f"tokens in/out {r.input_tokens}/{r.output_tokens}", flush=True)
    return r


def main(argv: list[str]) -> int:
    sc = load_scenario()
    run_id = make_run_id(sc, CONFIG)
    manifest = {"run_id": run_id, "scenario_id": sc["scenario_id"], "models": CONFIG["models"], "kb_version": CONFIG["kb"]["version"],
                "seed": CONFIG["seed"]}
    if "--baseline-only" not in argv:
        recs = run_grounded(sc, retriever=Retriever(get_embedder()), llm=verbose_llm, config=CONFIG, run_id=run_id)
        manifest["grounded_records"] = len(recs)
        for r in recs:
            flags = ",".join(f["flag"] for f in r["flags"]) or "-"
            print(f"{r['event_id']:<12} {r['agent']:<22} action={r['recommended_action']['action']:<34} evidence={r['evidence_status']:<38} flags={flags}")
    if "--grounded-only" not in argv:
        base = run_baseline(sc, llm=verbose_llm, config=CONFIG, run_id=run_id)
        manifest["baseline_records"] = len(base)
        print(f"baseline records: {len(base)}")
    (ROOT / "audit" / "runs" / f"{run_id}.manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"\nrun_id={run_id}\nreview proposals: python -m agents.approvals list {run_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
