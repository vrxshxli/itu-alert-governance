"""Gap Analyst: runs AFTER the simulation, over the audit records. Produces evidence-linked gaps, documentation limitations and
what held up well. It never manufactures gaps:

  * a gap needs (a) at least one audit record that raised NO_MANDATE_FOUND / COORDINATION_REQUIRED / AMBIGUOUS_PROVISION /
    CONFLICT_DETECTED, and (b) at least one evidence chunk that exists in the KB and whose text the verifier judges to support the
    observation. No evidence reference, no gap.
  * PUBLIC_DOCUMENTATION_LIMITATION flags are reported separately: the public corpus not establishing something is not a gap.
  * a global comparison must cite a reference_global source from the KB (FCC Hawaii 2018, EU EECC Art. 110/111, CAP/X.1303 bis).
  * severity carries a rationale; wording is domain-level and non-accusatory (lint below).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from agents import evidence as ev
from agents.jsonutil import extract_json
from kb.authority import registry

GAP_FLAGS = {"NO_MANDATE_FOUND", "COORDINATION_REQUIRED", "AMBIGUOUS_PROVISION", "CONFLICT_DETECTED"}
ABSENCE_TYPES = {"mandate_not_established", "decision_owner_unclear", "interface_unclear", "correction_procedure_not_established"}
GAP_TYPES = ["mandate_not_established", "decision_owner_unclear", "interface_unclear", "correction_procedure_not_established", "ambiguous_provision"]
SEVERITY = ["low", "medium", "high"]
BLAME = re.compile(r"\b(fail(ed|s|ure)? to|negligen\w*|incompeten\w*|blame\w*|at fault|fault of|culpab\w*|irresponsib\w*|"
                   r"should have known|dereliction)\b", re.I)

SYSTEM = (
    "You are a governance Gap Analyst reviewing the audit records of a FICTIONAL stress test of a published-policy knowledge base. "
    "You do not assess real institutions. Propose gaps in the PUBLISHED POLICY FRAMEWORK only where the records show an agent "
    "could not find or could not resolve something that the evidence passages show is unaddressed, ambiguous or shared.\n"
    "Rules: every gap cites evidence chunk ids copied exactly from EVIDENCE PASSAGES; do not invent chunk ids; no blame or "
    "accusation, speak about provisions and roles, not about people or institutions failing; direction is domain-level (what "
    "kind of clarification would help, not who must do it); anything the public documents simply do not contain (for example a "
    "regulation that is not published) is a documentation_limitation, not a gap; give severity (low|medium|high) with a one-sentence "
    "rationale; add a global_comparison only if a passage from a reference_global source genuinely shows how another system handles it.\n"
    "Return JSON only."
)


def wording_problems(text: str) -> list[str]:
    return [m.group(0) for m in BLAME.finditer(text or "")]


@dataclass
class Gap:
    gap_id: str
    type: str
    description: str
    evidence: list[dict]
    affected_institutions: list[str]
    severity: dict
    global_comparison: dict | None
    direction: str
    source_records: list[str]
    verified: bool = False
    verifier_notes: str = ""

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _flagged(records: list[dict]) -> list[dict]:
    return [r for r in records if any(f["flag"] in GAP_FLAGS for f in r["flags"])]


def _limitations(records: list[dict]) -> list[dict]:
    out = []
    for r in records:
        for f in r["flags"]:
            if f["flag"] == "PUBLIC_DOCUMENTATION_LIMITATION":
                out.append({"record": r["hash"], "event_id": r["event_id"], "agent": r["agent"], "why": f.get("why", "")})
    return out


def _held_up(records: list[dict]) -> list[dict]:
    out = []
    for r in records:
        for c in r["claims"]:
            if c.get("evidence_status") in ("confirmed", "partially_supported") and c.get("verifier_status") in ("supported", "partially_supported"):
                out.append({"record": r["hash"], "event_id": r["event_id"], "agent": r["agent"], "claim": c["text"],
                            "cited_chunk_ids": c["cited_chunk_ids"], "evidence_status": c["evidence_status"]})
    return out


def analyse(records: list[dict], retriever, llm: Callable, *, model: str, verifier_model: str) -> dict:
    """Returns {"gaps": [...], "documentation_limitations": [...], "held_up_well": [...], "dropped": [...]}."""
    flagged = _flagged(records)
    result = {"gaps": [], "documentation_limitations": _limitations(records), "held_up_well": _held_up(records), "dropped": []}
    if not flagged:
        return result  # nothing flagged: no gaps are manufactured
    ids = {c["chunk_id"] for r in records for c in r["retrieved_chunks"]}
    passages = {}
    for cid in ids:
        got = retriever.get(cid)
        if got:
            passages[cid] = got
    brief = "\n".join(
        f"- record {r['hash'][:12]} event {r['event_id']} agent {r['agent']}: flags {[(f['flag'], f['why']) for f in r['flags']]}; "
        f"summary: {r['reasoning_summary'][:300]}" for r in flagged)
    ev_text = "\n\n".join(f"[{cid}] ({p['metadata']['doc_id']}, {p['metadata']['article']}, {p['metadata']['authority_status']})\n{p['text'][:900]}"
                          for cid, p in passages.items())
    r = llm(f"FLAGGED RECORDS:\n{brief}\n\nEVIDENCE PASSAGES:\n{ev_text}\n\n"
            "Return JSON: {\"gaps\": [{\"gap_id\": \"G1\", \"type\": \"" + "|".join(GAP_TYPES) + "\", \"description\": \"...\", "
            "\"evidence\": [{\"chunk_id\": \"...\", \"why\": \"...\"}], \"affected_institutions\": [\"role names\"], "
            "\"severity\": {\"level\": \"low|medium|high\", \"rationale\": \"...\"}, "
            "\"global_comparison\": {\"chunk_id\": \"...\", \"why\": \"...\"} or null, \"direction\": \"domain-level\", "
            "\"source_records\": [\"12-char record hash prefixes\"]}]}",
            system=SYSTEM, model=model, max_tokens=6000, purpose="gap_analyst")
    j = extract_json(r.text) or {}
    flagged_prefix = {x["hash"][:12]: x["hash"] for x in flagged}
    for i, g in enumerate(j.get("gaps") or [], 1):
        gid = str(g.get("gap_id") or f"G{i}")
        why_drop = _structural_problem(g, passages, flagged_prefix, retriever)
        if why_drop:
            result["dropped"].append({"gap_id": gid, "reason": why_drop})
            continue
        # Verification depends on what the gap claims. A gap that says something is NOT established is a claim about absence: it cannot
        # be "supported" by a passage. It stands only if the cited passages are on topic and do not establish the thing, AND a broader
        # search of the KB finds no provision that does. (Changed 2026-11-08 after a real absence gap was dropped by the old
        # "do the passages support the description" check; see docs/CHANGELOG_DECISIONS.md.)
        shim = {e["chunk_id"]: _as_hit(e["chunk_id"], passages.get(e["chunk_id"]) or retriever.get(e["chunk_id"])) for e in g["evidence"]}
        if g.get("type") in ABSENCE_TYPES:
            ok, note = _verify_absence(g, shim, retriever, llm, verifier_model)
            if not ok:
                result["dropped"].append({"gap_id": gid, "reason": f"absence check failed ({note})"})
                continue
            verifier_notes = note
        else:
            claim = ev.Claim(text=g["description"], claim_type="fact", cited_chunk_ids=list(shim))
            ev.verify(ev.gate([claim], shim), shim, llm, verifier_model)
            if claim.verifier_status not in ("supported", "partially_supported"):
                result["dropped"].append({"gap_id": gid, "reason": f"evidence did not support the description ({claim.verifier_rationale})"})
                continue
            verifier_notes = claim.verifier_rationale
        gc = g.get("global_comparison")
        if gc:
            gc_chunk = retriever.get(gc.get("chunk_id", ""))
            if not gc_chunk or gc_chunk["metadata"]["authority_status"] != "reference_global":
                gc = None  # a comparison must cite a real global reference source
        result["gaps"].append(Gap(
            gap_id=gid, type=g.get("type") if g.get("type") in GAP_TYPES else "ambiguous_provision", description=g["description"].strip(),
            evidence=g["evidence"], affected_institutions=[str(x) for x in g.get("affected_institutions", [])],
            severity={"level": g["severity"]["level"], "rationale": g["severity"]["rationale"]}, global_comparison=gc,
            direction=str(g.get("direction", "")), source_records=[flagged_prefix[p] for p in g.get("source_records", []) if p in flagged_prefix],
            verified=True, verifier_notes=verifier_notes).as_dict())
    return result


def _verify_absence(g: dict, shim: dict, retriever, llm: Callable, verifier_model: str) -> tuple[bool, str]:
    """Absence check. Returns (ok, note). Two tests: (1) cited passages are on topic and do not establish the missing thing;
    (2) a broader search of current UAE sources finds no passage that establishes it."""
    passages = "\n\n".join(f"[{i}] {h.text[:1200]}" for i, h in shim.items())
    r = llm(f"WHAT THE GAP SAYS IS NOT ESTABLISHED: {g['description']}\n\nCITED PASSAGES:\n{passages}\n\n"
            "Do the passages, taken together, ESTABLISH the missing thing (a named owner, procedure or interface for exactly this)? "
            "Are the passages ON TOPIC for it? JSON only: {\"establishes\": true|false, \"on_topic\": true|false, \"rationale\": \"one sentence\"}",
            system="You judge strictly from the text given.", model=verifier_model, max_tokens=1500, purpose="gap_absence")
    j = extract_json(r.text) or {}
    if j.get("establishes") is True:
        return False, "the cited passages establish it: " + str(j.get("rationale", ""))[:160]
    if j.get("on_topic") is not True:
        return False, "the cited passages are not on topic: " + str(j.get("rationale", ""))[:160]
    found = []
    for h in retriever.search(g["description"], mode="current", n=12):
        rr = llm(f"MISSING THING: {g['description']}\n\nPASSAGE [{h.chunk_id}]: {h.text[:1200]}\n\nDoes this passage ESTABLISH the missing thing "
                 "(a named owner, procedure or interface for exactly this)? JSON only: {\"establishes\": true|false}",
                 system="You judge strictly from the text given.", model=verifier_model, max_tokens=500, purpose="gap_search_judge")
        if (extract_json(rr.text) or {}).get("establishes") is True:
            found.append(h.chunk_id)
    if found:
        return False, f"a broader search found passages that may establish it: {found}"
    return True, ("absence supported: cited passages are on topic and do not establish it; a 12-result search of current UAE sources "
                  "found nothing that does. " + str(j.get("rationale", ""))[:160])


def _as_hit(cid: str, got: dict):
    from kb.authority import format_citation
    from kb.retrieval import Hit

    m = got["metadata"]
    return Hit(chunk_id=cid, doc_id=m["doc_id"], article=m["article"], title=m["title"], url=m["url"], score=1.0, text=got["text"],
               translation_status=m["translation_status"], authority_status=m["authority_status"], arabic_text=m.get("arabic_text", ""),
               citation=format_citation(m["doc_id"], m["article"]))


def _structural_problem(g: dict, passages: dict, flagged_prefix: dict, retriever) -> str | None:
    if not isinstance(g, dict) or not str(g.get("description", "")).strip():
        return "empty description"
    evid = g.get("evidence") or []
    if not evid:
        return "no evidence references (no gap without evidence)"
    for e in evid:
        if not isinstance(e, dict) or not (e.get("chunk_id") in passages or retriever.get(str(e.get("chunk_id")))):
            return f"evidence chunk id not in the KB: {e.get('chunk_id') if isinstance(e, dict) else e}"
    sev = g.get("severity")
    if not isinstance(sev, dict) or sev.get("level") not in SEVERITY or not str(sev.get("rationale", "")).strip():
        return "severity needs a level and a rationale"
    if not any(p in flagged_prefix for p in g.get("source_records") or []):
        return "not traceable to any flagged audit record"
    bad = wording_problems(" ".join(str(g.get(k, "")) for k in ("description", "direction")))
    if bad:
        return f"accusatory wording: {bad}"
    return None
