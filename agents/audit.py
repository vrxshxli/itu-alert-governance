"""Append-only JSONL audit log: one record per agent step, hash-chained so edits are detectable.

Record fields (all required): ts, run_id, kb_version, model, event_id, agent, inputs_seen[], retrieved_chunks[{chunk_id,
doc_id, article, score}], reasoning_summary, claims[{text, cited_chunk_ids[], verifier_status, verifier_rationale}], flags[],
recommended_action, evidence_status, human_approval{required, status}, messages_sent[].
`prev_hash` and `hash` are added by the writer (sha256 over the canonical record plus the previous hash).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

REQUIRED = ["ts", "run_id", "kb_version", "model", "event_id", "agent", "inputs_seen", "retrieved_chunks", "reasoning_summary",
            "claims", "flags", "recommended_action", "evidence_status", "human_approval", "messages_sent"]
EVIDENCE = {"confirmed", "partially_supported", "not_established_from_public_sources"}
CLAIM_KEYS = {"text", "cited_chunk_ids", "verifier_status", "verifier_rationale"}


class AuditError(ValueError): ...


def validate(rec: dict) -> None:
    miss = [k for k in REQUIRED if k not in rec]
    if miss:
        raise AuditError(f"missing fields: {miss}")
    if rec["evidence_status"] not in EVIDENCE:
        raise AuditError(f"evidence_status must be one of {sorted(EVIDENCE)} (no numeric confidence): {rec['evidence_status']!r}")
    if set(rec["human_approval"]) < {"required", "status"}:
        raise AuditError("human_approval needs required and status")
    for c in rec["claims"]:
        if not CLAIM_KEYS <= set(c):
            raise AuditError(f"claim missing keys {CLAIM_KEYS - set(c)}")
    for r in rec["retrieved_chunks"]:
        if not {"chunk_id", "doc_id", "article", "score"} <= set(r):
            raise AuditError("retrieved_chunks entries need chunk_id, doc_id, article, score")


def _digest(rec: dict, prev: str) -> str:
    return hashlib.sha256((prev + json.dumps(rec, sort_keys=True, ensure_ascii=False)).encode("utf-8")).hexdigest()


class AuditLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._prev = "0" * 64
        if self.path.exists():
            lines = [l for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]
            if lines:
                self._prev = json.loads(lines[-1])["hash"]

    def append(self, rec: dict) -> dict:
        rec = {**rec}
        rec.setdefault("ts", time.time())
        validate(rec)
        out = {**rec, "prev_hash": self._prev}
        out["hash"] = _digest(rec, self._prev)
        with self.path.open("a", encoding="utf-8") as f:  # append mode only: no API rewrites earlier lines
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        self._prev = out["hash"]
        return out

    def read(self) -> list[dict]:
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()] if self.path.exists() else []


def verify_chain(path: Path) -> tuple[bool, str]:
    prev = "0" * 64
    for n, line in enumerate((l for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()), 1):
        r = json.loads(line)
        h, p = r.pop("hash"), r.pop("prev_hash")
        if p != prev or _digest(r, prev) != h:
            return False, f"chain broken at record {n}"
        prev = h
    return True, "chain intact"
