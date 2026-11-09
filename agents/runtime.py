"""Agent runtime: private inbox -> retrieve -> reason -> evidence gate -> verifier -> flag checks -> action gate -> audit record.

Each Agent sees only its own inbox. Retrieval, the model call and the verifier are injected so the whole pipeline is unit-tested
offline with fakes. Nothing an agent recommends is final: every non-trivial action is recorded with human_approval
{required: true, status: "pending"} and only `agents.approvals.final_decisions()` (approved by a human) counts as a decision.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from agents import evidence as ev
from agents.audit import AuditLog
from agents.jsonutil import extract_json
from agents.profiles import FLAGS, PROFILES, Profile

MESSAGE_KINDS = {"info_request", "status_report", "proposal"}  # a message can never be a decision
NO_APPROVAL_NEEDED = {"no_action"}


@dataclass
class Message:
    sender: str
    to: str
    kind: str
    content: str
    event_id: str


class Agent:
    def __init__(self, profile: Profile, retriever, llm: Callable, *, agent_model: str, verifier_model: str,
                 run_id: str, kb_version: str, audit: AuditLog, n_retrieve: int = 6, max_context: int = 14):
        self.p, self.retriever, self.llm = profile, retriever, llm
        self.agent_model, self.verifier_model = agent_model, verifier_model
        self.run_id, self.kb_version, self.audit = run_id, kb_version, audit
        self.n, self.max_context = n_retrieve, max_context
        self.inbox: list[dict] = []  # private: only this agent reads it

    def receive(self, item: dict) -> None:
        self.inbox.append(item)

    # ---- retrieval ----
    def _retrieve(self, inputs: list[str]) -> dict:
        """Three query families, merged: (1) one ANCHOR query per verified mandate statement in the profile, so the articles the
        profile rests on are always in front of the agent; (2) the role's standing query; (3) the event text."""
        queries = [(i.statement, 1) for i in self.p.established] + [(self.p.role_query, 3), (f"{self.p.role_query}. {' '.join(inputs)[:500]}", self.n)]
        merged: dict = {}
        for mode in self.p.retrieval_modes:
            for q, k in queries:
                for h in self.retriever.search(q, mode=mode, n=k):
                    if h.chunk_id not in merged or h.score > merged[h.chunk_id].score:
                        merged[h.chunk_id] = h
        top = sorted(merged.values(), key=lambda h: -h.score)[: self.max_context]
        return {h.chunk_id: h for h in top}

    def _prompt(self, event_id: str, inputs: list[str], retrieved: dict) -> str:
        passages = "\n\n".join(
            f"[{h.chunk_id}] {h.citation}\n{h.text[:1400]}" for h in retrieved.values()) or "(nothing retrieved)"
        return (
            f"EVENT {event_id}. Your private inbox (only you see this):\n" + "\n".join(f"- {x}" for x in inputs) +
            f"\n\nRETRIEVED PASSAGES (cite by the id in square brackets):\n{passages}\n\n"
            "CLAIMS are ONLY statements about what the published passages say or establish (type mandate, fact about a rule, or comparison). "
            "Statements about the scenario itself (what the inbox says, what you observe) belong in reasoning_summary, not in claims.\n"
            "Respond with JSON only:\n"
            "{\"reasoning_summary\": \"2-4 sentences, what you conclude and why\",\n"
            " \"claims\": [{\"text\": \"...\", \"type\": \"mandate|fact|comparison\", \"cited_chunk_ids\": [\"...\"]}],\n"
            f" \"flags\": [{{\"flag\": \"one of {FLAGS}\", \"why\": \"...\"}}],\n"
            f" \"recommended_action\": {{\"action\": \"one of {list(self.p.allowed_actions)}\", \"detail\": \"...\", "
            "\"human_authority_needed\": \"what a human must decide or authorise\"},\n"
            " \"messages\": [{\"to\": \"emergency_management|telecom_operator|policy_adviser\", "
            "\"kind\": \"info_request|status_report|proposal\", \"content\": \"...\"}]}"
        )

    # ---- flag handling ----
    def _check_flags(self, raw_flags: list, retrieved: dict, claims: list[ev.Claim], question: str) -> list[dict]:
        out = []
        for f in raw_flags or []:
            name = f.get("flag") if isinstance(f, dict) else None
            if name not in FLAGS:
                continue
            why = str(f.get("why", ""))[:300]
            if name == "NO_MANDATE_FOUND":
                better = self._recheck_no_mandate(question)
                if better:  # our retrieval may be at fault: do not promote this to a finding
                    out.append({"flag": "AMBIGUOUS_PROVISION", "why": f"NO_MANDATE_FOUND not accepted: re-check retrieved {better}", "rechecked": True})
                    continue
                why = (why + " [re-checked with a broader search: still nothing]").strip()
            out.append({"flag": name, "why": why})
        merged: dict[str, dict] = {}
        for f in out:  # one entry per flag name: repeated flags carry no extra information
            if f["flag"] in merged:
                merged[f["flag"]]["why"] = (merged[f["flag"]]["why"] + " | " + f["why"])[:400]
            else:
                merged[f["flag"]] = f
        out = list(merged.values())
        if ev.rejected(claims) and not any(x["flag"] == "UNSUPPORTED" for x in out):
            out.append({"flag": "UNSUPPORTED", "why": "one or more claims failed the evidence gate or verifier and were rewritten"})
        return out

    def _recheck_no_mandate(self, question: str) -> list[str]:
        """Broader search (more results, current mode); returns chunk ids that the verifier model judges relevant."""
        hits = self.retriever.search(question, mode="current", n=12)
        found = []
        for h in hits[:12]:
            r = self.llm(f"QUESTION: {question}\n\nPASSAGE [{h.chunk_id}]: {h.text[:1200]}\n\nDoes this passage directly address the question? "
                         "JSON only: {\"relevant\": true|false}", system="You judge relevance strictly.", model=self.verifier_model,
                         max_tokens=500, purpose="recheck_no_mandate")
            if (extract_json(r.text) or {}).get("relevant") is True:
                found.append(h.chunk_id)
        return found

    # ---- one step ----
    def step(self, event_id: str, inputs: list[str] | None = None) -> tuple[dict, list[Message]]:
        inputs = inputs if inputs is not None else [str(i["content"]) for i in self.inbox if i.get("event_id") == event_id]
        retrieved = self._retrieve(inputs)
        r = self.llm(self._prompt(event_id, inputs, retrieved), system=self.p.system_prompt(), model=self.agent_model,
                     purpose=f"agent_{self.p.agent_id}")
        j = extract_json(r.text)
        if j is None:  # a malformed answer must not become a decision
            j = {"reasoning_summary": "Model output could not be parsed; no claims accepted.", "claims": [], "flags": [],
                 "recommended_action": {"action": "no_action", "detail": "parse failure"}, "messages": []}
        claims = ev.verify(ev.gate(ev.parse_claims(j.get("claims")), retrieved), retrieved, self.llm, self.verifier_model)
        flags = self._check_flags(j.get("flags"), retrieved, claims, " ".join(inputs)[:400])

        act = j.get("recommended_action") if isinstance(j.get("recommended_action"), dict) else {}
        action = str(act.get("action", "no_action"))
        if action not in self.p.allowed_actions:  # action gate: only what the sources establish for this role
            flags.append({"flag": "UNSUPPORTED", "why": f"action '{action}' is outside the established mandate profile; replaced by no_action"})
            act = {"action": "no_action", "detail": f"blocked: '{action}' not allowed for {self.p.agent_id}", "blocked_action": action}
            action = "no_action"
        act.setdefault("human_authority_needed", "")

        msgs, sent = [], []
        for m in j.get("messages") or []:
            if isinstance(m, dict) and m.get("kind") in MESSAGE_KINDS and m.get("to") in PROFILES and m.get("to") != self.p.agent_id:
                msg = Message(self.p.agent_id, m["to"], m["kind"], str(m.get("content", ""))[:800], event_id)
                msgs.append(msg)
                sent.append({"to": msg.to, "kind": msg.kind, "content": msg.content})

        rec = self.audit.append({
            "run_id": self.run_id, "kb_version": self.kb_version, "model": self.agent_model, "event_id": event_id,
            "agent": self.p.agent_id, "inputs_seen": inputs, "retrieved_chunks": [h.brief() for h in retrieved.values()],
            "reasoning_summary": str(j.get("reasoning_summary", ""))[:1200], "claims": [c.audit() for c in claims],
            "flags": flags, "recommended_action": act, "evidence_status": ev.overall_status(claims),
            "human_approval": {"required": action not in NO_APPROVAL_NEEDED, "status": "pending" if action not in NO_APPROVAL_NEEDED else "not_required"},
            "messages_sent": sent, "verifier_model": self.verifier_model,
        })
        return rec, msgs
