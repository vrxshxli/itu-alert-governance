"""Offline tests for profiles, evidence gate/verifier, audit log, approvals and the agent runtime (fake LLM + fake retriever)."""
import json
from types import SimpleNamespace

import pytest

from agents import approvals, evidence as ev
from agents.audit import AuditError, AuditLog, verify_chain
from agents.profiles import FLAGS, PROFILES
from agents.runtime import Agent
from kb.authority import registry
from kb.retrieval import Hit


def hit(cid, doc, art, text, score=0.8, tstat="original", astat="current_authoritative"):
    return Hit(chunk_id=cid, doc_id=doc, article=art, title="t", url="https://example.org/" + doc, score=score, text=text,
               translation_status=tstat, authority_status=astat, arabic_text="", citation=f"{doc}, {art}")


NCEMA5 = hit("ae-dl-2-2011-ncema-en-unofficial:art5", "ae-dl-2-2011-ncema-en-unofficial", "Art. 5",
             "The Authority shall coordinate the roles of the relevant bodies when emergencies occur.", tstat="unofficial_translation")
LIC8 = hit("ae-tdra-licence-3-2026:art8", "ae-tdra-licence-3-2026", "Art. 8",
           "If a competent authority declares a public emergency the Licensee shall comply with directions.", tstat="official_translation_arabic_prevails")
FCC = hit("us-fcc-hawaii-2018:w010", "us-fcc-hawaii-2018", "p. 3", "The false alert took 38 minutes to correct.", astat="reference_global")
COORD = hit("ae-dl-8-2025-faacd:art4:p1", "ae-dl-8-2025-faacd", "Art. 4",
            "Establish a public warning system for the population, in coordination with the National Emergency, Crisis and Disasters Management Authority.")


class FakeRetriever:
    def __init__(self, hits):
        self.hits = hits

    def search(self, q, mode="current", n=5):
        pool = [h for h in self.hits if (mode != "global") == (h.authority_status != "reference_global")] if mode in ("current", "global") else self.hits
        return pool[:n]


def fake_llm(agent_json=None, verdicts=None, relevant=False):
    verdicts = verdicts or {}

    def call(prompt, *, system="", model=None, max_tokens=None, purpose="", use_cache=True):
        if purpose == "verifier":
            for key, v in verdicts.items():
                if key in prompt:
                    return SimpleNamespace(text=json.dumps(v))
            return SimpleNamespace(text=json.dumps({"verdict": "supported", "coordination_only": False, "rationale": "ok"}))
        if purpose == "recheck_no_mandate":
            return SimpleNamespace(text=json.dumps({"relevant": relevant}))
        return SimpleNamespace(text=agent_json if isinstance(agent_json, str) else json.dumps(agent_json))
    return call


# ---------- profiles ----------
def _verified(doc_id, article):
    reg = registry()
    return article in (reg[doc_id].get("articles_verified") or [])


def test_every_profile_statement_cites_a_verified_article():
    for p in PROFILES.values():
        for item in p.established:
            assert item.sources, p.agent_id
            for doc, art in item.sources:
                assert _verified(doc, art), f"{p.agent_id} cites unverified {doc} {art}"


def test_profiles_never_allow_what_they_forbid_and_never_grant_alert_powers():
    for p in PROFILES.values():
        assert not set(p.allowed_actions) & set(p.forbidden_actions)
        assert not any(a.startswith(("issue", "cancel", "retract", "originate")) for a in p.allowed_actions)
    assert "issue_alert" in PROFILES["emergency_management"].forbidden_actions
    assert any("issues, authorises, triggers" in x for x in PROFILES["emergency_management"].not_established)


def test_prompt_contains_not_established_and_flags():
    s = PROFILES["emergency_management"].system_prompt()
    assert "do NOT establish" in s and all(f in s for f in FLAGS)


# ---------- evidence gate + verifier ----------
def test_gate_rejects_uncited_and_unretrieved():
    claims = ev.parse_claims([{"text": "a", "type": "mandate", "cited_chunk_ids": []},
                              {"text": "b", "type": "mandate", "cited_chunk_ids": ["not:retrieved"]},
                              {"text": "c", "type": "fact", "cited_chunk_ids": [LIC8.chunk_id]}])
    ev.gate(claims, {LIC8.chunk_id: LIC8})
    assert [c.verifier_status for c in claims] == ["failed_gate", "failed_gate", "unverified"]


def test_unsupported_claim_rewritten_and_flagged():
    claims = ev.parse_claims([{"text": "NCEMA triggers alerts", "type": "mandate", "cited_chunk_ids": [NCEMA5.chunk_id]}])
    ev.gate(claims, {NCEMA5.chunk_id: NCEMA5})
    llm = fake_llm(verdicts={"triggers alerts": {"verdict": "unsupported", "coordination_only": False, "rationale": "not stated"}})
    ev.verify(claims, {NCEMA5.chunk_id: NCEMA5}, llm, "m")
    assert claims[0].text == ev.NO_MANDATE_TEXT and claims[0].original_text == "NCEMA triggers alerts"
    assert claims[0].evidence_status == ev.NOT_EST and ev.overall_status(claims) == ev.NOT_EST


def test_coordination_clause_rejected_as_mandate_evidence():
    r = {COORD.chunk_id: COORD}
    claims = ev.parse_claims([{"text": "NCEMA operates the public warning system", "type": "mandate", "cited_chunk_ids": [COORD.chunk_id]}])
    ev.gate(claims, r)
    llm = fake_llm(verdicts={"operates": {"verdict": "supported", "coordination_only": True, "rationale": "only 'in coordination with'"}})
    ev.verify(claims, r, llm, "m")
    assert claims[0].text == ev.NO_MANDATE_TEXT and "coordination clause" in claims[0].verifier_rationale


def test_unofficial_translation_capped_at_partially_supported():
    r = {NCEMA5.chunk_id: NCEMA5}
    claims = ev.parse_claims([{"text": "coordinates roles", "type": "mandate", "cited_chunk_ids": [NCEMA5.chunk_id]}])
    ev.gate(claims, r)
    ev.verify(claims, r, fake_llm(), "m")
    assert claims[0].verifier_status == "supported" and claims[0].evidence_status == "partially_supported"


def test_official_source_can_be_confirmed_and_global_cannot_ground_mandate():
    r = {LIC8.chunk_id: LIC8, FCC.chunk_id: FCC}
    claims = ev.parse_claims([{"text": "licensee must comply", "type": "mandate", "cited_chunk_ids": [LIC8.chunk_id]},
                              {"text": "US agency must do X so UAE agency must", "type": "mandate", "cited_chunk_ids": [FCC.chunk_id]},
                              {"text": "Hawaii took 38 minutes", "type": "comparison", "cited_chunk_ids": [FCC.chunk_id]}])
    ev.gate(claims, r)
    ev.verify(claims, r, fake_llm(), "m")
    assert claims[0].evidence_status == "confirmed"
    assert claims[1].text == ev.NO_MANDATE_TEXT
    assert claims[2].verifier_status == "supported" and claims[2].evidence_status == "confirmed"


# ---------- audit ----------
REC = dict(run_id="r", kb_version="k", model="m", event_id="E1", agent="a", inputs_seen=[], retrieved_chunks=[], reasoning_summary="",
           claims=[], flags=[], recommended_action={"action": "no_action"}, evidence_status="not_established_from_public_sources",
           human_approval={"required": False, "status": "not_required"}, messages_sent=[])


def test_audit_rejects_numeric_confidence_and_missing_fields(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    with pytest.raises(AuditError):
        log.append({**REC, "evidence_status": "0.93"})
    bad = {k: v for k, v in REC.items() if k != "agent"}
    with pytest.raises(AuditError):
        log.append(bad)


def test_audit_chain_detects_tampering(tmp_path):
    p = tmp_path / "a.jsonl"
    log = AuditLog(p)
    log.append(REC)
    log.append({**REC, "event_id": "E2"})
    assert verify_chain(p)[0]
    p.write_text(p.read_text().replace('"E1"', '"E9"', 1))
    assert not verify_chain(p)[0]
    log2 = AuditLog(tmp_path / "b.jsonl")  # a reopened log continues the chain
    log2.append(REC)
    AuditLog(tmp_path / "b.jsonl").append(REC)
    assert verify_chain(tmp_path / "b.jsonl")[0]


# ---------- runtime ----------
def make_agent(tmp_path, pid, llm, hits):
    return Agent(PROFILES[pid], FakeRetriever(hits), llm, agent_model="am", verifier_model="vm", run_id="run1", kb_version="kb-test",
                 audit=AuditLog(tmp_path / "run1.jsonl"))


GOOD = {"reasoning_summary": "Coordinate.", "claims": [{"text": "Coordinates roles.", "type": "mandate", "cited_chunk_ids": [NCEMA5.chunk_id]}],
        "flags": [], "recommended_action": {"action": "convene_coordination", "detail": "convene", "human_authority_needed": "approve"},
        "messages": [{"to": "telecom_operator", "kind": "info_request", "content": "status?"}]}


def test_step_writes_complete_audit_record_and_message(tmp_path):
    a = make_agent(tmp_path, "emergency_management", fake_llm(GOOD), [NCEMA5, LIC8])
    rec, msgs = a.step("E1", ["Reports of an unexpected alert."])
    assert rec["agent"] == "emergency_management" and rec["model"] == "am" and rec["kb_version"] == "kb-test"
    assert rec["human_approval"] == {"required": True, "status": "pending"}
    assert rec["claims"][0]["evidence_status"] == "partially_supported" and rec["evidence_status"] == "partially_supported"
    assert msgs[0].to == "telecom_operator" and msgs[0].kind == "info_request"
    assert verify_chain(tmp_path / "run1.jsonl")[0]


def test_forbidden_action_is_blocked_and_flagged(tmp_path):
    bad = {**GOOD, "recommended_action": {"action": "cancel_alert", "detail": "cancel it"}}
    rec, _ = make_agent(tmp_path, "emergency_management", fake_llm(bad), [NCEMA5]).step("E1", ["x"])
    assert rec["recommended_action"]["action"] == "no_action" and rec["recommended_action"]["blocked_action"] == "cancel_alert"
    assert any(f["flag"] == "UNSUPPORTED" for f in rec["flags"])
    assert rec["human_approval"]["required"] is False


def test_message_cannot_be_a_decision_or_go_to_self(tmp_path):
    bad = {**GOOD, "messages": [{"to": "telecom_operator", "kind": "decision", "content": "cancel now"},
                                {"to": "emergency_management", "kind": "info_request", "content": "self"}]}
    rec, msgs = make_agent(tmp_path, "emergency_management", fake_llm(bad), [NCEMA5]).step("E1", ["x"])
    assert msgs == [] and rec["messages_sent"] == []


def test_unparseable_model_output_yields_no_claims_and_no_action(tmp_path):
    rec, _ = make_agent(tmp_path, "emergency_management", fake_llm("not json at all"), [NCEMA5]).step("E1", ["x"])
    assert rec["claims"] == [] and rec["recommended_action"]["action"] == "no_action"
    assert rec["evidence_status"] == "not_established_from_public_sources"


def test_no_mandate_flag_is_rechecked_and_not_promoted_when_retrieval_finds_something(tmp_path):
    j = {**GOOD, "claims": [], "flags": [{"flag": "NO_MANDATE_FOUND", "why": "nothing"}]}
    rec, _ = make_agent(tmp_path, "emergency_management", fake_llm(j, relevant=True), [NCEMA5, LIC8]).step("E1", ["x"])
    assert [f["flag"] for f in rec["flags"]] == ["AMBIGUOUS_PROVISION"] and rec["flags"][0]["rechecked"]
    rec2, _ = make_agent(tmp_path, "emergency_management", fake_llm(j, relevant=False), [NCEMA5, LIC8]).step("E2", ["x"])
    assert rec2["flags"][0]["flag"] == "NO_MANDATE_FOUND" and "re-checked" in rec2["flags"][0]["why"]


def test_adviser_sees_global_sources_but_cannot_use_them_as_mandate(tmp_path):
    j = {"reasoning_summary": "compare", "flags": [], "messages": [],
         "recommended_action": {"action": "compare_with_global_example", "detail": "d"},
         "claims": [{"text": "Hawaii took 38 minutes", "type": "comparison", "cited_chunk_ids": [FCC.chunk_id]},
                    {"text": "UAE operator must cancel within minutes", "type": "mandate", "cited_chunk_ids": [FCC.chunk_id]}]}
    rec, _ = make_agent(tmp_path, "policy_adviser", fake_llm(j), [NCEMA5, FCC]).step("E1", ["x"])
    ids = {c["chunk_id"] for c in rec["retrieved_chunks"]}
    assert FCC.chunk_id in ids
    assert rec["claims"][0]["evidence_status"] == "confirmed" and rec["claims"][1]["text"] == ev.NO_MANDATE_TEXT


def test_inboxes_are_private(tmp_path):
    a = make_agent(tmp_path, "emergency_management", fake_llm(GOOD), [NCEMA5])
    b = make_agent(tmp_path, "telecom_operator", fake_llm(GOOD), [LIC8])
    a.receive({"event_id": "E2", "content": "public reports"})
    assert b.inbox == [] and a.inbox[0]["content"] == "public reports"


# ---------- approvals ----------
def test_only_human_approved_records_become_final(tmp_path, monkeypatch):
    monkeypatch.setattr(approvals, "RUNS", tmp_path)
    a = make_agent(tmp_path, "emergency_management", fake_llm(GOOD), [NCEMA5])
    rec, _ = a.step("E1", ["x"])
    assert approvals.final_decisions("run1") == []
    assert [r["hash"] for r in approvals.pending("run1")] == [rec["hash"]]
    with pytest.raises(ValueError):
        approvals.decide("run1", rec["hash"], "approved", "  ")
    approvals.decide("run1", rec["hash"], "approved", "Shivam", "ok")
    assert [r["hash"] for r in approvals.final_decisions("run1")] == [rec["hash"]] and approvals.pending("run1") == []
    with pytest.raises(ValueError):
        approvals.decide("run1", rec["hash"], "rejected", "Shivam")


# ---------- changes after the first live run ----------
def test_current_mode_is_uae_only_and_global_mode_is_non_uae_on_real_chroma():
    """Regression: an international technical standard leaked into 'current' results (cited by the telecom agent as if UAE law)."""
    import chromadb

    from kb.authority import combined_where

    col = chromadb.EphemeralClient().get_or_create_collection("scope_test", metadata={"hnsw:space": "cosine"})
    rows = [("uae-law", "UAE", "current_authoritative"), ("uae-ts", "UAE", "technical_standard"), ("uae-old", "UAE", "historical_repealed"),
            ("cap", "international", "technical_standard"), ("fcc", "US", "reference_global"), ("y3172", "international", "framework")]
    col.add(ids=[r[0] for r in rows], documents=[r[0] for r in rows], embeddings=[[1.0, 0.1 * i] for i in range(len(rows))],
            metadatas=[{"jurisdiction": r[1], "authority_status": r[2]} for r in rows])
    ids = lambda mode: set(col.query(query_embeddings=[[1.0, 0.0]], n_results=6, where=combined_where(mode))["ids"][0])
    assert ids("current") == {"uae-law", "uae-ts"}
    assert ids("global") == {"cap", "fcc"}
    assert ids("history") == {"uae-law", "uae-ts", "uae-old"}
    assert ids("framework") == {"y3172"}


class QueryRecorder(FakeRetriever):
    def __init__(self, hits):
        super().__init__(hits)
        self.queries = []

    def search(self, q, mode="current", n=5):
        self.queries.append((q, mode, n))
        return super().search(q, mode=mode, n=n)


def test_anchor_queries_use_each_verified_mandate_statement(tmp_path):
    rr = QueryRecorder([NCEMA5, LIC8])
    a = Agent(PROFILES["telecom_operator"], rr, fake_llm(GOOD), agent_model="am", verifier_model="vm", run_id="r", kb_version="k",
              audit=AuditLog(tmp_path / "r.jsonl"))
    a.step("E1", ["A very long scenario text " * 40])
    sent = [q for q, _, _ in rr.queries]
    for item in PROFILES["telecom_operator"].established:
        assert item.statement in sent  # the profile's own articles are always searched for, whatever the event says
    assert all(len(q) < 700 for q in sent)


def test_repeated_flags_are_merged_into_one(tmp_path):
    j = {**GOOD, "flags": [{"flag": "AMBIGUOUS_PROVISION", "why": "a"}, {"flag": "AMBIGUOUS_PROVISION", "why": "b"},
                           {"flag": "COORDINATION_REQUIRED", "why": "c"}]}
    rec, _ = make_agent(tmp_path, "emergency_management", fake_llm(j), [NCEMA5]).step("E1", ["x"])
    names = [f["flag"] for f in rec["flags"]]
    assert names == ["AMBIGUOUS_PROVISION", "COORDINATION_REQUIRED"] and "a" in rec["flags"][0]["why"] and "b" in rec["flags"][0]["why"]


def test_prompt_keeps_scenario_facts_out_of_claims(tmp_path):
    seen = {}

    def spy(prompt, *, system="", model=None, max_tokens=None, purpose="", use_cache=True):
        if purpose.startswith("agent_"):
            seen["prompt"] = prompt
        return fake_llm(GOOD)(prompt, system=system, model=model, max_tokens=max_tokens, purpose=purpose)

    make_agent(tmp_path, "emergency_management", spy, [NCEMA5]).step("E1", ["x"])
    assert "Statements about the scenario itself" in seen["prompt"] and "belong in reasoning_summary" in seen["prompt"]
