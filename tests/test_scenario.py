"""Scenario engine tests (fake LLM + fake retriever): visibility, ordering, bounded message passing, baseline format."""
import json

from agents.audit import verify_chain
from scenario.engine import FOLLOWUP_ROUNDS, load_scenario, make_run_id, run_baseline, run_grounded
from tests.test_agents import FakeRetriever, LIC8, NCEMA5, FCC, fake_llm

CONFIG = {"models": {"agent": "am", "cheap": "vm"}, "kb": {"version": "kb-test"}}


def agent_json(to=None):
    return {"reasoning_summary": "r", "claims": [{"text": "Coordinates roles.", "type": "mandate", "cited_chunk_ids": [NCEMA5.chunk_id]}],
            "flags": [], "recommended_action": {"action": "no_action", "detail": ""},
            "messages": [{"to": to, "kind": "info_request", "content": "status?"}] if to else []}


def test_scenario_file_is_valid_and_matches_brief():
    sc = load_scenario()
    ev = {e["event_id"]: e for e in sc["events"]}
    assert list(ev) == ["E1", "E2", "E3", "E4", "E5", "E6"]
    assert ev["E2"]["visible_to"] == ["emergency_management"]  # public reports go to Emergency Management
    assert [e["t_offset"] for e in sc["events"]] == sorted(e["t_offset"] for e in sc["events"])
    text = json.dumps(sc).lower()
    assert "missile" not in text  # civil governance only; never call it a missile alert
    # information is uneven: no single event is visible to everyone
    assert all(len(e["visible_to"]) < 3 for e in sc["events"])


def test_events_reach_only_their_recipients_and_in_time_order(tmp_path):
    sc = load_scenario()
    recs = run_grounded(sc, retriever=FakeRetriever([NCEMA5, LIC8, FCC]), llm=fake_llm(agent_json()), config=CONFIG, run_id="t1", runs_dir=tmp_path)
    seen = {}
    for r in recs:
        seen.setdefault(r["agent"], []).append(r["event_id"])
    assert seen["telecom_operator"] == ["E1", "E3", "E5"]
    assert seen["emergency_management"] == ["E2", "E4", "E6"]
    assert seen["policy_adviser"] == ["E4", "E6"]
    ts = [r["ts"] for r in recs]
    assert ts == sorted(ts)
    for r in recs:  # an agent's inputs never include an event it was not shown
        for x in r["inputs_seen"]:
            assert "Network monitoring" not in x or r["agent"] == "telecom_operator"
    assert verify_chain(tmp_path / "t1.jsonl")[0]


def test_message_passing_is_bounded_and_private(tmp_path):
    sc = load_scenario()
    # emergency_management asks telecom_operator something on E2; telecom replies by message too (must NOT loop forever)
    llm_em = agent_json("telecom_operator")
    recs = run_grounded(sc, retriever=FakeRetriever([NCEMA5, LIC8]), llm=fake_llm(llm_em), config=CONFIG, run_id="t2", runs_dir=tmp_path)
    follow = [r for r in recs if r["event_id"].endswith("+followup")]
    assert follow, "recipients get one follow-up step"
    per_event = {}
    for r in follow:
        per_event.setdefault(r["event_id"], 0)
        per_event[r["event_id"]] += 1
    assert max(per_event.values()) <= 3 and FOLLOWUP_ROUNDS == 1
    # the recipient of an E2 message saw the message text, but not E2's raw content
    f2 = [r for r in follow if r["event_id"] == "E2+followup" and r["agent"] == "telecom_operator"][0]
    assert any("Message from emergency_management" in x for x in f2["inputs_seen"])
    assert not any("Public reports (unverified" in x for x in f2["inputs_seen"])


def test_baseline_has_no_retrieval_and_same_visibility(tmp_path):
    sc = load_scenario()
    base = {"reasoning_summary": "b", "claims": [{"text": "NCEMA issues alerts", "type": "mandate", "citation": "Decree-Law 2/2011 Art. 5"}],
            "flags": [], "recommended_action": {"action": "issue_alert", "detail": "x"}}
    recs = run_baseline(sc, llm=fake_llm(base), config=CONFIG, run_id="t3", runs_dir=tmp_path)
    assert len(recs) == sum(len(e["visible_to"]) for e in sc["events"])
    assert all(r["retrieved_chunks"] == [] and r["agent"].startswith("baseline:") for r in recs)
    assert recs[0]["claims"][0]["citation_text"] == "Decree-Law 2/2011 Art. 5"
    assert recs[0]["kb_version"].startswith("none")
    assert verify_chain(tmp_path / "t3.baseline.jsonl")[0]


def test_run_id_changes_with_models():
    sc = load_scenario()
    a = make_run_id(sc, CONFIG)
    b = make_run_id(sc, {"models": {"agent": "other", "cheap": "vm"}, "kb": {"version": "kb-test"}})
    assert a.split("-")[-1] != b.split("-")[-1]
