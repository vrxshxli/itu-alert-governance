"""Scorecard: plain LLM (no KB) versus KB-grounded, on the SAME scenario, scored by the SAME verifier against the KB.

Metrics (counts and percentages; no significance claims; one run each):
  1. citation validity %   share of claims whose citation resolves to a KB chunk that the verifier says supports the claim
  2. unsupported mandate claims   mandate claims that fail verification. Grounded: before the gate (what the agent proposed)
     and after it (what survived); baseline has no gate so both are the same
  3. missing mandates correctly flagged   of the topics the sources are known NOT to establish, how many the run explicitly says
     are not established (judged by the cheap model; spot-check the judge in the CSV)
  4. verifiable gaps   gaps whose evidence references resolve to KB chunks the verifier says support them (gap report only;
     the baseline produces no chunk-linked evidence, so 0 by construction, said so in the output)
A manual spot-check CSV of ~20 claims (seeded sample, both conditions) is written for a human to fill in.
"""
from __future__ import annotations

import csv
import random
import re
from pathlib import Path
from typing import Callable

from agents import evidence as ev
from agents.jsonutil import extract_json

# Topics that kb/AUTHORITY_RULES.md records as NOT established by the read sources.
NOT_ESTABLISHED_TOPICS = {
    "T1": "which body issues or authorises a public alert",
    "T2": "which body cancels or corrects an alert that was already delivered, and how",
    "T3": "which authority is the 'competent authority' that directs an operator in a public emergency",
    "T4": "the content of the Executive Regulation that sets event classification and each body's role",
}
DOC_PATTERNS = [  # citation text -> registry doc whose chunk ids we can check (current in-force UAE sources in the KB)
    (r"(2\s*/\s*2011|\b2\s*of\s*2011|ncema)", "ae-dl-2-2011-ncema-en-unofficial"),
    (r"(8\s*/\s*2025|\b8\s*of\s*2025)", "ae-dl-8-2025-faacd"),
    (r"(3\s*/\s*2003|\b3\s*of\s*2003)", "ae-dl-3-2003-telecom"),
    (r"(34\s*/\s*2021|\b34\s*of\s*2021)", "ae-dl-34-2021-rumours"),
    (r"(45\s*/\s*2021|\b45\s*of\s*2021)", "ae-dl-45-2021-pdpl"),
    (r"(licen[cs]e.*2026|3\s*/\s*2026)", "ae-tdra-licence-3-2026"),
    (r"(ts\s*fs\s*001)", "ae-tdra-ts-fs-001"),
    (r"(2018\s*/\s*1972|european electronic communications code)", "eu-eecc-2018-1972"),
]


def resolve_citation(text: str, retriever) -> list[str]:
    """Free-text citation -> KB chunk ids ([] if it cannot be resolved to a chunk that exists)."""
    t = (text or "").lower()
    doc = next((d for pat, d in DOC_PATTERNS if re.search(pat, t)), None)
    if not doc:
        return []
    m = re.search(r"art(?:icle)?s?\.?\s*\(?\s*(\d+)", t)
    if doc == "ae-tdra-ts-fs-001":
        cands = [f"{doc}:w{n:03d}" for n in range(1, 9)]
    elif not m:
        return []
    else:
        base = f"{doc}:art{m.group(1)}"
        cands = [base] + [f"{base}:p{k}" for k in range(1, 7)]
    return [c for c in cands if retriever.get(c)]


def _hit(retriever, cid):
    from agents.gap_analyst import _as_hit

    return _as_hit(cid, retriever.get(cid))


def _ok(verifier_status: str) -> bool:
    return verifier_status in ("supported", "partially_supported")


def score_grounded(records: list[dict]) -> dict:
    """Grounded claims were already gated and verified at run time; read the outcome from the audit records."""
    rows, n, valid = [], 0, 0
    proposed = rejected = surviving_unsupported = mandate_valid = 0
    for r in records:
        for c in r["claims"]:
            n += 1
            ok = _ok(c["verifier_status"])
            valid += ok
            mandate = c.get("claim_type") == "mandate"
            proposed += mandate
            mandate_valid += mandate and ok
            rejected += mandate and bool(c.get("original_text"))
            surviving_unsupported += mandate and not c.get("original_text") and not ok
            rows.append({"condition": "grounded", "event": r["event_id"], "agent": r["agent"], "claim": c.get("original_text") or c["text"],
                         "type": c.get("claim_type", ""), "citation": ", ".join(c["cited_chunk_ids"]) or "(none)",
                         "verifier": "pass" if ok else "fail"})
    return {"claims": n, "valid": valid, "validity_pct": round(100 * valid / n, 1) if n else None,
            "mandate_claims_proposed": proposed, "mandate_valid": mandate_valid, "mandate_claims_rejected_by_gate": rejected,
            "unsupported_mandate_claims_surviving": surviving_unsupported, "rows": rows}


UNCITED = re.compile(r"(not known|no specific|none known|unknown|unable to cite|do not know|don't know|no .{0,40}provision.{0,20}known|^\s*$)", re.I)


def score_baseline(records: list[dict], retriever, llm: Callable, verifier_model: str) -> dict:
    """Baseline claims carry free-text citations: resolve each to KB chunks, then run the SAME verifier. No gate exists, so every
    failing mandate claim survives into the output. Each claim lands in exactly one bucket so nothing is hidden in the headline:
      uncited               the model named no specific provision (e.g. 'No specific UAE provision known'): an honest gap, but the claim
                            is unsupported if it asserts a mandate
      cited_not_in_kb       it named a provision we cannot map to a KB chunk (other law, no article, outside the KB): unverifiable here
      resolved_unsupported  it resolves to a KB chunk but the verifier says the chunk does not support the claim (or cannot ground a mandate)
      valid                 resolves to a KB chunk and the verifier says it supports the claim"""
    rows, n, valid = [], 0, 0
    buckets = {"uncited": 0, "cited_not_in_kb": 0, "resolved_unsupported": 0, "valid": 0}
    mandate_n = mandate_ok = 0
    for r in records:
        for c in r["claims"]:
            n += 1
            cit = c.get("citation_text", "")
            ids = resolve_citation(cit, retriever)
            claim = ev.Claim(text=c["text"], claim_type=c.get("claim_type", "fact"), cited_chunk_ids=ids)
            shim = {i: _hit(retriever, i) for i in ids}
            ev.verify(ev.gate([claim], shim), shim, llm, verifier_model)
            ok = _ok(claim.verifier_status)
            if ok:
                bucket = "valid"
            elif ids:
                bucket = "resolved_unsupported"
            elif UNCITED.search(cit or ""):
                bucket = "uncited"
            else:
                bucket = "cited_not_in_kb"
            buckets[bucket] += 1
            valid += ok
            mandate = claim.claim_type == "mandate"
            mandate_n += mandate
            mandate_ok += mandate and ok
            rows.append({"condition": "baseline", "event": r["event_id"], "agent": r["agent"], "claim": c["text"], "type": claim.claim_type,
                         "citation": (cit or "(none)") + ("" if ids else f"  [{bucket}]"), "verifier": "pass" if ok else "fail"})
    cited = n - buckets["uncited"]
    return {"claims": n, "valid": valid, "validity_pct": round(100 * valid / n, 1) if n else None, "buckets": buckets,
            "cited_claims": cited, "validity_pct_of_cited": round(100 * valid / cited, 1) if cited else None,
            "mandate_claims_proposed": mandate_n, "mandate_valid": mandate_ok,
            "unsupported_mandate_claims_surviving": mandate_n - mandate_ok, "rows": rows}


def run_summary(records: list[dict]) -> str:
    parts = []
    for r in records:
        parts.append(f"[{r['agent']} {r['event_id']}] {r['reasoning_summary']}")
        parts += [f"claim: {c.get('original_text') or c['text']}" for c in r["claims"]]
        parts += [f"flag {f['flag']}: {f.get('why', '')}" for f in r["flags"]]
        if r["recommended_action"].get("detail"):
            parts.append(f"action: {r['recommended_action'].get('detail')}")
    return "\n".join(parts)[:14000]


def missing_flagged(records: list[dict], llm: Callable, model: str) -> dict:
    text = run_summary(records)
    out = {}
    for tid, topic in NOT_ESTABLISHED_TOPICS.items():
        r = llm(f"RUN OUTPUT:\n{text}\n\nTopic: {topic}.\nDoes the run output EXPLICITLY say that the published sources do not establish "
                "this topic (or flag its absence/ambiguity), as opposed to asserting an answer? JSON only: "
                "{\"flagged_as_not_established\": true|false, \"asserts_an_answer\": true|false, \"quote\": \"short quote or empty\"}",
                system="You judge strictly from the text given.", model=model, max_tokens=1500, purpose="scorecard_topic_judge")
        out[tid] = {"topic": topic, **(extract_json(r.text) or {"flagged_as_not_established": False, "asserts_an_answer": False, "quote": "unparseable"})}
    return {"topics": out, "correctly_flagged": sum(bool(v.get("flagged_as_not_established")) for v in out.values()), "of": len(out)}


def spot_check_csv(rows: list[dict], path: Path, n: int = 20, seed: int = 26250) -> None:
    rng = random.Random(seed)
    g = [r for r in rows if r["condition"] == "grounded"]
    b = [r for r in rows if r["condition"] == "baseline"]
    pick = rng.sample(g, min(n // 2, len(g))) + rng.sample(b, min(n - n // 2, len(b)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["condition", "event", "agent", "type", "claim", "citation", "verifier", "human_verdict", "human_note"])
        w.writeheader()
        for r in pick:
            w.writerow({**{k: r[k] for k in ("condition", "event", "agent", "type", "claim", "citation", "verifier")}, "human_verdict": "", "human_note": ""})
