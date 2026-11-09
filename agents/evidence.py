"""Evidence gate and claim-level verifier.

Gate (code, no model): a claim stands only if it cites at least one chunk id that was actually retrieved for this step, and
every cited chunk has a url, an article and a chunk id.
Verifier (cheap model, one call per claim): reads the claim and ONLY the cited chunks and judges support. A mandate claim
supported only by a coordination clause, by a global comparison source, or by a repealed law is rejected (rules R2, R4-R6).
Unsupported claims are rewritten to NO_MANDATE_TEXT and flagged UNSUPPORTED.
Evidence labels are categorical (confirmed / partially_supported / not_established_from_public_sources), never numeric, and
are capped by the source registry (e.g. unofficial translations cannot exceed partially_supported).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from agents.jsonutil import extract_json
from kb.authority import EVIDENCE_ORDER, cap_evidence, can_support_current_mandate

NO_MANDATE_TEXT = "No published mandate located in the available knowledge base."
NOT_EST = "not_established_from_public_sources"
CLAIM_TYPES = {"mandate", "fact", "comparison"}

VERIFIER_SYSTEM = (
    "You are a strict legal-evidence verifier. You see one CLAIM and the cited PASSAGES only. Decide whether the passages "
    "themselves support the claim. Do not use outside knowledge.\n"
    "Return JSON only: {\"verdict\": \"supported\"|\"partial\"|\"unsupported\", \"coordination_only\": true|false, \"rationale\": \"one or two sentences\"}.\n"
    "- supported: the passages state what the claim says.\n"
    "- partial: the passages support part of it, or support it only by inference.\n"
    "- unsupported: the passages do not say it.\n"
    "- coordination_only: true if the claim says a body OWNS, OPERATES, TRIGGERS, AUTHORISES or CANCELS something but the "
    "passages only say that body acts 'in coordination with' another, is consulted, is informed or may comment.\n"
)


@dataclass
class Claim:
    text: str
    claim_type: str
    cited_chunk_ids: list[str]
    verifier_status: str = "unverified"
    verifier_rationale: str = ""
    evidence_status: str = NOT_EST
    original_text: str | None = None

    def audit(self) -> dict:
        return {"text": self.text, "cited_chunk_ids": self.cited_chunk_ids, "verifier_status": self.verifier_status,
                "verifier_rationale": self.verifier_rationale, "claim_type": self.claim_type,
                "evidence_status": self.evidence_status, **({"original_text": self.original_text} if self.original_text else {})}


def parse_claims(raw: list[dict] | None) -> list[Claim]:
    out = []
    for c in raw or []:
        if not isinstance(c, dict) or not str(c.get("text", "")).strip():
            continue
        t = c.get("type", "fact")
        out.append(Claim(text=str(c["text"]).strip(), claim_type=t if t in CLAIM_TYPES else "fact",
                         cited_chunk_ids=[str(i) for i in (c.get("cited_chunk_ids") or [])]))
    return out


def gate(claims: list[Claim], retrieved: dict) -> list[Claim]:
    """Structural evidence gate. `retrieved` maps chunk_id -> Hit (needs url, article, chunk_id)."""
    for c in claims:
        valid = [i for i in c.cited_chunk_ids if i in retrieved and retrieved[i].url and retrieved[i].article and retrieved[i].chunk_id]
        if not valid:
            c.verifier_status = "failed_gate"
            c.verifier_rationale = "no cited chunk id was retrieved for this step" if c.cited_chunk_ids else "no citation"
        c.cited_chunk_ids = valid
    return claims


def verify(claims: list[Claim], retrieved: dict, llm: Callable, model: str) -> list[Claim]:
    for c in claims:
        if c.verifier_status == "failed_gate":
            _reject(c)
            continue
        passages = "\n\n".join(f"[{i}] ({retrieved[i].citation})\n{retrieved[i].text[:1500]}" for i in c.cited_chunk_ids)
        r = llm(f"CLAIM ({c.claim_type}): {c.text}\n\nPASSAGES:\n{passages}", system=VERIFIER_SYSTEM, model=model,
                max_tokens=1500, purpose="verifier")
        j = extract_json(r.text) or {}
        verdict = j.get("verdict", "unsupported")
        c.verifier_rationale = str(j.get("rationale", ""))[:400]
        docs = [retrieved[i].doc_id for i in c.cited_chunk_ids]
        mandate = c.claim_type == "mandate"
        if verdict not in ("supported", "partial"):
            c.verifier_status = "unsupported"
            _reject(c)
        elif mandate and j.get("coordination_only") is True:
            c.verifier_status = "unsupported"
            c.verifier_rationale = ("REJECTED (coordination clause is not mandate evidence): " + c.verifier_rationale)[:400]
            _reject(c)
        elif mandate and not any(can_support_current_mandate(d.replace("-en-unofficial", "")) for d in docs):
            c.verifier_status = "unsupported"
            c.verifier_rationale = ("REJECTED (cited sources cannot ground a current UAE mandate: repealed, global or framework): "
                                    + c.verifier_rationale)[:400]
            _reject(c)
        else:
            c.verifier_status = "supported" if verdict == "supported" else "partially_supported"
            requested = "confirmed" if verdict == "supported" else "partially_supported"
            c.evidence_status = cap_evidence(requested, docs, current_mandate_claim=mandate)
    return claims


def _reject(c: Claim) -> None:
    c.original_text = c.text
    c.text = NO_MANDATE_TEXT
    c.evidence_status = NOT_EST


def overall_status(claims: list[Claim]) -> str:
    live = [c for c in claims if c.verifier_status in ("supported", "partially_supported")]
    if not live:
        return NOT_EST
    return min((c.evidence_status for c in live), key=EVIDENCE_ORDER.index)


def rejected(claims: list[Claim]) -> bool:
    return any(c.original_text for c in claims)
