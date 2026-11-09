"""Enforcement of kb/AUTHORITY_RULES.md: source authority filters, evidence caps and citation formatting.

Pure functions over the registry in kb/sources.yaml so they can be unit-tested before any agent exists.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

REGISTRY = Path(__file__).resolve().parent / "sources.yaml"

EVIDENCE_ORDER = ["not_established_from_public_sources", "partially_supported", "confirmed"]
CURRENT_AUTHORITY = {"current_authoritative"}
NEVER_CURRENT = {"historical_repealed"}


@lru_cache
def registry() -> dict[str, dict]:
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for s in data["sources"]:
        out[s["doc_id"]] = s
        for t in s.get("translations", []) or []:
            out[t["doc_id"]] = {**s, **t, "translation_of": s["doc_id"], "translations": []}
    return out


def where_filter(mode: str = "current") -> dict:
    """ChromaDB `where` clause. 'current' excludes repealed law and framework docs; 'history' allows repealed law;
    'global' returns comparison sources only."""
    if mode == "current":
        return {"authority_status": {"$in": ["current_authoritative", "technical_standard"]}}
    if mode == "global":
        return {"authority_status": {"$in": ["reference_global", "technical_standard"]}}
    if mode == "framework":  # ITU-T Y.3172 and the AI Readiness Framework: alignment references, never mandates
        return {"authority_status": "framework"}
    if mode == "history":
        return {"authority_status": {"$in": ["current_authoritative", "historical_repealed", "technical_standard"]}}
    raise ValueError(mode)


def jurisdiction_filter(mode: str) -> dict | None:
    """'current' and 'history' are UAE sources only; 'global' is non-UAE comparison sources only (FCC, EU, ITU CAP). Without this,
    an international technical standard leaked into the telecom agent's 'current' results and was cited as if it were UAE law."""
    if mode in ("current", "history"):
        return {"jurisdiction": "UAE"}
    if mode == "global":
        return {"jurisdiction": {"$ne": "UAE"}}
    return None


def combined_where(mode: str) -> dict:
    j = jurisdiction_filter(mode)
    return {"$and": [where_filter(mode), j]} if j else where_filter(mode)


def can_support_current_mandate(doc_id: str) -> bool:
    """Only in-force UAE law/regulation can ground a current institutional mandate (R4, R5, R6)."""
    s = registry()[doc_id]
    return s["authority_status"] in CURRENT_AUTHORITY and s.get("jurisdiction") == "UAE" and "Strategy" not in s["title"]


def cap_evidence(requested: str, doc_ids: list[str], *, current_mandate_claim: bool) -> str:
    """Return the highest evidence label allowed given the supporting sources.
    A claim is limited by its BEST supporting source (one authoritative source suffices)."""
    if requested not in EVIDENCE_ORDER:
        raise ValueError(requested)
    if not doc_ids:
        return "not_established_from_public_sources"
    best = "not_established_from_public_sources"
    for d in doc_ids:
        s = registry()[d]
        ceiling = s.get("max_evidence_status", "confirmed")
        if current_mandate_claim and not can_support_current_mandate(d):
            ceiling = "not_established_from_public_sources"
        if EVIDENCE_ORDER.index(ceiling) > EVIDENCE_ORDER.index(best):
            best = ceiling
    return EVIDENCE_ORDER[min(EVIDENCE_ORDER.index(requested), EVIDENCE_ORDER.index(best))]


def format_citation(doc_id: str, article: str, arabic_article: str | None = None) -> str:
    """Citation string. Unofficial translations always point at the Arabic original (R1)."""
    s = registry()[doc_id]
    if s.get("translation_status") == "unofficial_translation":
        orig = registry()[s["translation_of"]]
        art = arabic_article or article
        return (f"{orig['title']}, {art} (Arabic original, authoritative): {orig['url']} "
                f"[English text is an unofficial translation, non-authoritative]")
    tag = ""
    if s.get("translation_status") == "official_translation_arabic_prevails":
        tag = " [official English translation; Arabic text prevails]"
    if s["authority_status"] == "historical_repealed":
        tag += f" [REPEALED: {s['currency_note']}]"
    return f"{s['title']}, {article}: {s['url']}{tag}"


# R2: phrases that express coordination only. A provision matching these is never, on its own, evidence that the
# coordinated-with institution holds the power in question.
COORDINATION_ONLY_PATTERNS = ("in coordination with", "in cooperation with", "after coordination with",
                              "coordinate with", "in consultation with")


def is_coordination_only(provision_text: str, institution: str, power_holder_named_as_subject: bool) -> bool:
    """True when `institution` appears in the provision only as a coordination partner. The verifier calls this
    before accepting a provision as evidence that `institution` holds a power."""
    t = provision_text.lower()
    i = institution.lower()
    return (not power_holder_named_as_subject) and any(f"{p} {i}" in t or f"{p} the {i}" in t
                                                       for p in COORDINATION_ONLY_PATTERNS)
