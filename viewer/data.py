"""Data layer for the local viewer (no model calls, no network). Reads audit/runs/*, report/* and the KB; writes only through
agents.approvals (human decisions, append-only).

Safety: run ids are matched against a strict pattern (no path traversal); the HTTP server binds to 127.0.0.1 only; an approval
needs a non-empty human name and can only target a record that is still pending."""
from __future__ import annotations

import json
import re
from pathlib import Path

from agents import approvals
from agents.audit import verify_chain
from kb.authority import format_citation
from scenario.engine import load_scenario

ROOT = Path(__file__).resolve().parents[1]
RUN_RE = re.compile(r"^run-\d{8}-\d{6}-[0-9a-f]{8}$")
EXCERPT = 700

FLAG_MEANING = {
    "NO_MANDATE_FOUND": "Retrieval found no provision (re-checked with a broader search before being accepted).",
    "PUBLIC_DOCUMENTATION_LIMITATION": "The public corpus does not establish it. Not a policy gap.",
    "AMBIGUOUS_PROVISION": "A provision exists but can be read more than one way.",
    "CONFLICT_DETECTED": "Two provisions point in different directions.",
    "COORDINATION_REQUIRED": "More than one body is named and the text does not say who decides.",
    "UNSUPPORTED": "A claim failed the evidence gate or verifier and was rewritten.",
}


def _read(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []


def list_runs(runs_dir: Path | None = None) -> list[str]:
    d = runs_dir or ROOT / "audit" / "runs"
    return sorted((p.name[: -len(".manifest.json")] for p in d.glob("*.manifest.json") if RUN_RE.match(p.name[: -len(".manifest.json")])), reverse=True)


def load_run(run_id: str, runs_dir: Path | None = None) -> dict:
    if not RUN_RE.match(run_id):
        raise ValueError("bad run id")
    d = runs_dir or ROOT / "audit" / "runs"
    g, b = d / f"{run_id}.jsonl", d / f"{run_id}.baseline.jsonl"
    decided = {x["record_hash"]: x for x in _read(d / f"{run_id}.approvals.jsonl")}
    chain = {name: (verify_chain(p) if p.exists() else (False, "missing")) for name, p in (("grounded", g), ("baseline", b))}
    manifest = json.loads((d / f"{run_id}.manifest.json").read_text(encoding="utf-8")) if (d / f"{run_id}.manifest.json").exists() else {}
    return {"run_id": run_id, "manifest": manifest, "scenario": load_scenario(), "grounded": _read(g), "baseline": _read(b),
            "approvals": decided, "chain": {k: {"ok": v[0], "message": v[1]} for k, v in chain.items()}, "flag_meaning": FLAG_MEANING}


def report_bundle(report_dir: Path | None = None) -> dict:
    d = report_dir or ROOT / "report"
    out = {}
    for key, name in (("gap_report", "gap_report.md"), ("scorecard", "scorecard.md")):
        p = d / name
        out[key] = p.read_text(encoding="utf-8") if p.exists() else f"_{name} not generated yet: run scripts/make_report.py_"
    p = d / "gap_analysis.json"
    out["gap_analysis"] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    return out


def chunk_info(chunk_id: str, collection=None, with_text: bool = True) -> dict | None:
    """Citation and (optionally) a short excerpt for one KB chunk. NCEMA chunks always cite the Arabic original."""
    if collection is None:
        import chromadb
        import yaml

        cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
        collection = chromadb.PersistentClient(path=str(ROOT / cfg["kb"]["chroma_dir"])).get_collection(cfg["kb"]["collection"])
    r = collection.get(ids=[chunk_id], include=["documents", "metadatas"])
    if not r["ids"]:
        return None
    m, t = r["metadatas"][0], r["documents"][0]
    info = {"chunk_id": chunk_id, "doc_id": m["doc_id"], "article": m["article"], "authority_status": m["authority_status"],
            "translation_status": m["translation_status"], "url": m["url"], "citation": format_citation(m["doc_id"], m["article"])}
    if with_text:
        info["excerpt"] = t[:EXCERPT] + ("..." if len(t) > EXCERPT else "")
    return info


def approve(run_id: str, record_hash: str, decision: str, by: str, note: str = "", runs_dir: Path | None = None) -> dict:
    if not RUN_RE.match(run_id):
        raise ValueError("bad run id")
    if runs_dir is not None:
        approvals.RUNS = runs_dir
    pend = {r["hash"] for r in approvals.pending(run_id)}
    if record_hash not in pend:
        raise ValueError("record is not pending (unknown hash or already decided)")
    return approvals.decide(run_id, record_hash, decision, by, note)
