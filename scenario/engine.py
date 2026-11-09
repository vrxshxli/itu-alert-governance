"""Scenario engine: progressive, uneven event release; private inboxes; bounded message passing; grounded and baseline runs.

Round structure per event (events sorted by t_offset):
  1. deliver the event to its visible_to agents' PRIVATE inboxes only
  2. step those agents (retrieval-grounded)
  3. deliver their messages to the recipients' inboxes; step each recipient once more in a bounded follow-up round
     (max FOLLOWUP_ROUNDS), so information can travel but cannot loop
A message is never a decision (agents.runtime.MESSAGE_KINDS); nothing is final until a human approves it (agents.approvals).

The baseline run gives the SAME roles the SAME inbox contents with NO knowledge base: a plain model answering from memory,
asked to cite specific provisions. Its claims are scored later by the same verifier against the KB.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Callable

import yaml

from agents.audit import AuditLog
from agents.jsonutil import extract_json
from agents.profiles import FLAGS, PROFILES
from agents.runtime import Agent, Message

ROOT = Path(__file__).resolve().parents[1]
FOLLOWUP_ROUNDS = 1
CORE_AGENTS = ["emergency_management", "telecom_operator", "policy_adviser"]


def load_scenario(path: Path | None = None) -> dict:
    sc = yaml.safe_load((path or ROOT / "scenario" / "events.yaml").read_text(encoding="utf-8"))
    ids = [e["event_id"] for e in sc["events"]]
    assert len(ids) == len(set(ids)) == 6, "scenario must have six distinct events"
    for e in sc["events"]:
        assert {"event_id", "t_offset", "visible_to", "content", "uncertainty"} <= set(e)
        assert set(e["visible_to"]) <= set(PROFILES), e["event_id"]
    return sc


def make_run_id(scenario: dict, config: dict, tag: str = "") -> str:
    h = hashlib.sha256(json.dumps([scenario, config["models"], config["kb"]["version"], tag], sort_keys=True).encode()).hexdigest()[:8]
    return f"run-{time.strftime('%Y%m%d-%H%M%S')}-{h}"


def run_grounded(scenario: dict, *, retriever, llm: Callable, config: dict, run_id: str, runs_dir: Path | None = None,
                 agents: list[str] | None = None) -> list[dict]:
    audit = AuditLog((runs_dir or ROOT / "audit" / "runs") / f"{run_id}.jsonl")
    ids = agents or CORE_AGENTS
    team = {a: Agent(PROFILES[a], retriever, llm, agent_model=config["models"]["agent"], verifier_model=config["models"]["cheap"],
                     run_id=run_id, kb_version=config["kb"]["version"], audit=audit) for a in ids}
    records: list[dict] = []
    for ev in sorted(scenario["events"], key=lambda e: e["t_offset"]):
        text = f"{ev['content']} (Uncertainty: {ev['uncertainty']})"
        active = [a for a in ev["visible_to"] if a in team]
        for a in active:
            team[a].receive({"event_id": ev["event_id"], "t_offset": ev["t_offset"], "content": text, "source": "event"})
        pending: list[Message] = []
        for a in active:
            rec, msgs = team[a].step(ev["event_id"])
            records.append(rec)
            pending += msgs
        for _ in range(FOLLOWUP_ROUNDS):
            if not pending:
                break
            by: dict[str, list[Message]] = {}
            for m in pending:
                if m.to in team:
                    team[m.to].receive({"event_id": ev["event_id"], "content": f"Message from {m.sender} ({m.kind}): {m.content}", "source": f"message:{m.sender}"})
                    by.setdefault(m.to, []).append(m)
            pending = []
            for a in by:
                inputs = [i["content"] for i in team[a].inbox if i["event_id"] == ev["event_id"]]
                rec, msgs = team[a].step(ev["event_id"] + "+followup", inputs)
                records.append(rec)
                # a follow-up's own messages are recorded in the audit log but not delivered (bounded: no loops)
    return records


BASELINE_SYSTEM = (
    "You are the {name} in a FICTIONAL public-alert governance exercise. {role} You have no document access: answer from your own "
    "knowledge. Jurisdiction of the exercise: the United Arab Emirates (federal level); other jurisdictions are comparisons only. "
    "State what your institution is mandated to do and which provision says so. Cite specific provisions as free text "
    "(law name, number, article). CLAIMS are only statements about what published rules say or establish; statements about the "
    "scenario itself belong in reasoning_summary. If you do not know of a provision, say so instead of guessing. Output JSON only."
)


def run_baseline(scenario: dict, *, llm: Callable, config: dict, run_id: str, runs_dir: Path | None = None,
                 agents: list[str] | None = None) -> list[dict]:
    """Same roles, same visibility, same event text, no KB. One answer per agent per visible event; records go to an audit
    log in the same format (retrieved_chunks empty, claims unverified) so scoring uses identical tooling."""
    audit = AuditLog((runs_dir or ROOT / "audit" / "runs") / f"{run_id}.baseline.jsonl")
    ids = agents or CORE_AGENTS
    seen = {a: [] for a in ids}
    out = []
    for ev in sorted(scenario["events"], key=lambda e: e["t_offset"]):
        for a in ev["visible_to"]:
            if a not in ids:
                continue
            seen[a].append(f"{ev['content']} (Uncertainty: {ev['uncertainty']})")
            p = PROFILES[a]
            prompt = ("Your private inbox so far:\n" + "\n".join(f"- {x}" for x in seen[a]) +
                      "\n\nRespond with JSON only: {\"reasoning_summary\": \"...\", \"claims\": [{\"text\": \"...\", \"type\": \"mandate|fact|comparison\", "
                      "\"citation\": \"law, number, article\"}], \"flags\": [], \"recommended_action\": {\"action\": \"...\", \"detail\": \"...\"}}")
            r = llm(prompt, system=BASELINE_SYSTEM.format(name=p.name, role=p.role_summary), model=config["models"]["agent"],
                    max_tokens=12000, purpose=f"baseline_{a}")
            j = extract_json(r.text) or {"reasoning_summary": "unparseable", "claims": [], "flags": [], "recommended_action": {"action": "no_action"}}
            claims = [{"text": str(c.get("text", "")), "cited_chunk_ids": [], "verifier_status": "unverified", "verifier_rationale": "",
                       "claim_type": c.get("type", "fact"), "citation_text": str(c.get("citation", ""))}
                      for c in j.get("claims", []) if isinstance(c, dict)]
            act = j.get("recommended_action") if isinstance(j.get("recommended_action"), dict) else {"action": "no_action"}
            rec = audit.append({"run_id": run_id, "kb_version": "none (baseline: no KB)", "model": config["models"]["agent"],
                                "event_id": ev["event_id"], "agent": f"baseline:{a}", "inputs_seen": list(seen[a]),
                                "retrieved_chunks": [], "reasoning_summary": str(j.get("reasoning_summary", ""))[:1200], "claims": claims,
                                "flags": [f for f in j.get("flags", []) if isinstance(f, dict) and f.get("flag") in FLAGS],
                                "recommended_action": act, "evidence_status": "not_established_from_public_sources",
                                "human_approval": {"required": True, "status": "pending"}, "messages_sent": []})
            out.append(rec)
    return out
