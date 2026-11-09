"""Human approval gate. Agents only ever write `pending` proposals; a decision becomes final only when a human records
`approved` here. Append-only JSONL beside the run's audit log: audit/runs/<run_id>.approvals.jsonl.

  python -m agents.approvals list <run_id>
  python -m agents.approvals decide <run_id> <record_hash_prefix> approved|rejected "<your name>" "<note>"
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "audit" / "runs"
DECISIONS = {"approved", "rejected"}


def _path(run_id: str) -> Path:
    return RUNS / f"{run_id}.approvals.jsonl"


def pending(run_id: str) -> list[dict]:
    recs = [json.loads(l) for l in (RUNS / f"{run_id}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    decided = {d["record_hash"] for d in _read(run_id)}
    return [r for r in recs if r["human_approval"]["required"] and r["hash"] not in decided]


def _read(run_id: str) -> list[dict]:
    p = _path(run_id)
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def decide(run_id: str, record_hash: str, decision: str, by: str, note: str = "", runs_dir: Path | None = None) -> dict:
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {DECISIONS}")
    if not by.strip():
        raise ValueError("a named human must decide")
    if any(d["record_hash"] == record_hash for d in _read(run_id)):
        raise ValueError("already decided; decisions are append-only")
    entry = {"ts": time.time(), "run_id": run_id, "record_hash": record_hash, "decision": decision, "by": by, "note": note}
    _path(run_id).parent.mkdir(parents=True, exist_ok=True)
    with _path(run_id).open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def final_decisions(run_id: str) -> list[dict]:
    """Audit records whose recommended action a named human approved. Everything else is a proposal, not a decision."""
    ok = {d["record_hash"]: d for d in _read(run_id) if d["decision"] == "approved"}
    recs = [json.loads(l) for l in (RUNS / f"{run_id}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    return [{**r, "approval": ok[r["hash"]]} for r in recs if r["hash"] in ok]


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "list":
        for r in pending(argv[1]):
            a = r["recommended_action"]
            print(f"{r['hash'][:12]}  {r['event_id']}  {r['agent']:<22} {a['action']}: {str(a.get('detail',''))[:90]}")
        return 0
    if len(argv) >= 5 and argv[0] == "decide":
        run_id, prefix, decision, by = argv[1:5]
        match = [r for r in pending(run_id) if r["hash"].startswith(prefix)]
        if len(match) != 1:
            print(f"hash prefix matched {len(match)} pending records")
            return 1
        decide(run_id, match[0]["hash"], decision, by, argv[5] if len(argv) > 5 else "")
        print("recorded")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
