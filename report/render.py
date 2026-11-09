"""Render the evidence-linked policy gap report (Markdown) from the Gap Analyst output. Citations are formatted by
kb.authority.format_citation, so NCEMA entries always show the Arabic source URL and the non-authoritative label.
No source text is reproduced: the report holds citations, our own paraphrases and the agents' verified claims."""
from __future__ import annotations

import json
from pathlib import Path

from kb.authority import format_citation

CORE_CLAIM = ("This project does not assess UAE institutions. It tests whether a published-policy knowledge base enables "
              "accountable, evidence-grounded coordination during a hypothetical public-alert governance failure.")
CLOSING = ("The system does not decide who is right. It shows what the published evidence supports, what it does not establish, "
           "and where human authority is required.")
ROLE = {"emergency_management": "Emergency Management role", "telecom_operator": "Telecom/Operator role", "policy_adviser": "Policy Adviser role"}


MAX_HELD, MAX_LIM = 14, 8


def _distinct(items: list[dict], key) -> list[dict]:
    seen, out = set(), []
    for i in items:
        k = key(i)
        if k not in seen:
            seen.add(k)
            out.append(i)
    return out


def _gap_label(retriever, g: dict) -> str:
    """A gap that rests on the unofficial NCEMA translation can be at most partially_supported (kb/authority.py)."""
    ids = [e["chunk_id"] for e in g["evidence"]]
    metas = [retriever.get(i)["metadata"] for i in ids if retriever.get(i)]
    if any(m["translation_status"] == "unofficial_translation" for m in metas):
        return ("partially_supported: it cites articles of the NCEMA law through the unofficial English translation; the Arabic original is the "
                "authority and each article should be checked against it before this is relied on")
    return "confirmed by the cited official sources" if metas else "not_established_from_public_sources"


def cite(retriever, chunk_id: str) -> str:
    got = retriever.get(chunk_id)
    if not got:
        return f"{chunk_id} (not found in KB)"
    m = got["metadata"]
    return f"`{chunk_id}`: " + format_citation(m["doc_id"], m["article"])


def render(analysis: dict, retriever, *, run_id: str, kb_version: str, models: dict, scenario: dict, approvals: dict | None = None,
           scorecard_path: str | None = None) -> str:
    L = ["# Evidence-linked policy gap report", "", f"> {CORE_CLAIM}", "",
         "The scenario is hypothetical and fictional (`DISCLAIMER.md`). Findings are about what the published documents establish, not about any institution's conduct.", "",
         f"Run `{run_id}` · knowledge base `{kb_version}` · agent model `{models['agent']}` · verifier model `{models['cheap']}`", "",
         "## 1. Scenario", ""]
    for e in sorted(scenario["events"], key=lambda e: e["t_offset"]):
        L.append(f"- **{e['event_id']}** (t+{e['t_offset']} min; visible to: {', '.join(ROLE[a] for a in e['visible_to'])}): {e['content']}")
    L += ["", "## 2. What held up well", ""]
    hw = _distinct(analysis["held_up_well"], key=lambda h: " ".join(h["claim"].lower().split())[:120])
    hw = sorted(hw, key=lambda h: (h["evidence_status"] != "confirmed", h["event_id"]))
    total = len(analysis["held_up_well"])
    if hw:
        L.append(f"{total} claims passed the evidence gate and verifier; {len(hw)} distinct ones are summarised below (up to {MAX_HELD}).")
        L.append("")
        for h in hw[:MAX_HELD]:
            ids = ", ".join(cite(retriever, c) for c in h["cited_chunk_ids"])
            L.append(f"- ({h['event_id']}, {ROLE.get(h['agent'], h['agent'])}; evidence: {h['evidence_status']}) {h['claim']}  \n  Sources: {ids}")
    else:
        L.append("- No claim passed the evidence gate and verifier in this run.")
    L += ["", "## 3. Policy gaps (each tied to evidence)", ""]
    if not analysis["gaps"]:
        L.append("No gap met the evidence requirements in this run. Gaps are never added without evidence.")
    for g in analysis["gaps"]:
        L += [f"### {g['gap_id']}: {g['type'].replace('_', ' ')}", "", g["description"], "",
              f"- **Affected roles:** {', '.join(g['affected_institutions']) or 'n/a'}",
              f"- **Severity:** {g['severity']['level']}. Rationale: {g['severity']['rationale']}",
              f"- **Direction (domain level):** {g['direction']}", "- **Evidence:**"]
        for e in g["evidence"]:
            L.append(f"  - {cite(retriever, e['chunk_id'])}. {e.get('why', '')}")
        if g["global_comparison"]:
            c = g["global_comparison"]
            L.append(f"- **Global comparison:** {cite(retriever, c['chunk_id'])}. {c.get('why', '')}")
        L += [f"- **Evidence label:** {_gap_label(retriever, g)}",
              f"- **Traceable to audit records:** {', '.join(h[:12] for h in g['source_records'][:3])}" + (f" (+{len(g['source_records']) - 3} more)" if len(g['source_records']) > 3 else ""),
              f"- **Verifier note:** {g['verifier_notes']}", ""]
    L += ["## 4. Documentation limitations (not policy gaps)", "",
          "Things the public corpus does not establish, for example detail delegated to an Executive Regulation that is not in the knowledge base. "
          "They say something about what could be checked, not about the policy.", ""]
    lim = _distinct(analysis["documentation_limitations"], key=lambda d: " ".join(d["why"].lower().split())[:90])
    if lim:
        L.append(f"Raised {len(analysis['documentation_limitations'])} times across the run; {len(lim)} distinct statements (up to {MAX_LIM}):")
        L.append("")
        for d in lim[:MAX_LIM]:
            L.append(f"- ({d['event_id']}, {ROLE.get(d['agent'], d['agent'])}) {d['why']}")
    else:
        L.append("- None flagged in this run.")
    L += ["", "## 5. Candidate gaps rejected by the evidence rules", ""]
    if analysis["dropped"]:
        L += [f"- {d['gap_id']}: {d['reason']}" for d in analysis["dropped"]]
    else:
        L.append("- None.")
    if approvals is not None:
        L += ["", "## 6. Human decisions", "",
              f"Proposals pending human approval: {approvals.get('pending', 0)}; approved by a named human: {approvals.get('approved', 0)}; rejected: {approvals.get('rejected', 0)}. "
              "Only approved items are decisions."]
    if scorecard_path:
        L += ["", f"Scorecard (plain LLM versus KB-grounded): `{scorecard_path}`."]
    L += ["", "---", f"*{CLOSING}*", ""]
    return "\n".join(L)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
