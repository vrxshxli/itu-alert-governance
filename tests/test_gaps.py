"""Gap analyst, report renderer and scorecard tests (fake LLM + fake KB)."""
import json
from types import SimpleNamespace

from agents.gap_analyst import analyse, wording_problems
from report.render import CLOSING, CORE_CLAIM, render
from scenario import scorecard
from scenario.engine import load_scenario

KB = {
    "ae-dl-2-2011-ncema-en-unofficial:art5": ("The Authority coordinates the roles of the relevant bodies.",
        {"doc_id": "ae-dl-2-2011-ncema-en-unofficial", "article": "Art. 5", "title": "t", "url": "https://u/ar", "translation_status": "unofficial_translation", "authority_status": "current_authoritative"}),
    "ae-dl-8-2025-faacd:art4:p1": ("Establish a public warning system, in coordination with the National Emergency Authority.",
        {"doc_id": "ae-dl-8-2025-faacd", "article": "Art. 4", "title": "t", "url": "https://u/8", "translation_status": "official_translation_arabic_prevails", "authority_status": "current_authoritative"}),
    "us-fcc-hawaii-2018:w010": ("The agency lacked a procedure for a false alert; correction took 38 minutes.",
        {"doc_id": "us-fcc-hawaii-2018", "article": "p. 3", "title": "t", "url": "https://u/fcc", "translation_status": "original", "authority_status": "reference_global"}),
}


class KBStub:
    def search(self, q, mode="current", n=5):
        from agents.gap_analyst import _as_hit

        return [_as_hit(c, self.get(c)) for c in KB if KB[c][1]["authority_status"] == "current_authoritative"][:n]

    def get(self, cid):
        if cid not in KB:
            return None
        t, m = KB[cid]
        return {"text": t, "metadata": {**m, "chunk_id": cid}}


def rec(h, flags, agent="emergency_management", event="E6", chunks=("ae-dl-2-2011-ncema-en-unofficial:art5", "ae-dl-8-2025-faacd:art4:p1")):
    return {"hash": h * 64, "event_id": event, "agent": agent, "flags": flags, "reasoning_summary": "s",
            "retrieved_chunks": [{"chunk_id": c, "doc_id": "d", "article": "a", "score": 0.5} for c in chunks],
            "claims": [], "recommended_action": {"action": "no_action", "detail": ""}}


GAP = {"gap_id": "G1", "type": "decision_owner_unclear", "description": "The provisions name several bodies for warning but none is stated to decide who corrects a delivered alert.",
       "evidence": [{"chunk_id": "ae-dl-8-2025-faacd:art4:p1", "why": "establishing a system, in coordination"}],
       "affected_institutions": ["Emergency Management role"], "severity": {"level": "high", "rationale": "affects the public"},
       "global_comparison": {"chunk_id": "us-fcc-hawaii-2018:w010", "why": "no correction procedure existed"}, "direction": "Clarify at framework level who decides corrections.",
       "source_records": ["a" * 12]}


def llm(gaps, verdict="supported", establishes=False, on_topic=True, search_establishes=()):
    def call(prompt, *, system="", model=None, max_tokens=None, purpose="", use_cache=True):
        if purpose == "gap_analyst":
            return SimpleNamespace(text=json.dumps({"gaps": gaps}))
        if purpose == "gap_absence":
            return SimpleNamespace(text=json.dumps({"establishes": establishes, "on_topic": on_topic, "rationale": "r"}))
        if purpose == "gap_search_judge":
            return SimpleNamespace(text=json.dumps({"establishes": any(c in prompt for c in search_establishes)}))
        return SimpleNamespace(text=json.dumps({"verdict": verdict, "coordination_only": False, "rationale": "stated"}))
    return call


def run(gaps, records, **kw):
    return analyse(records, KBStub(), llm(gaps, **kw), model="m", verifier_model="v")


FLAGGED = [rec("a", [{"flag": "COORDINATION_REQUIRED", "why": "who decides?"}])]


def test_no_flags_means_no_gaps_even_if_model_proposes_some():
    out = run([GAP], [rec("a", [])])
    assert out["gaps"] == []


def test_gap_with_evidence_flag_and_comparison_is_kept():
    out = run([GAP], FLAGGED)
    assert [g["gap_id"] for g in out["gaps"]] == ["G1"] and out["gaps"][0]["global_comparison"]["chunk_id"] == "us-fcc-hawaii-2018:w010"


def test_gap_without_evidence_dropped():
    out = run([{**GAP, "evidence": []}], FLAGGED)
    assert out["gaps"] == [] and "no gap without evidence" in out["dropped"][0]["reason"]


def test_gap_with_invented_chunk_id_dropped():
    out = run([{**GAP, "evidence": [{"chunk_id": "made:up", "why": "x"}]}], FLAGGED)
    assert out["gaps"] == [] and "not in the KB" in out["dropped"][0]["reason"]


def test_gap_not_traceable_to_flagged_record_dropped():
    out = run([{**GAP, "source_records": ["b" * 12]}], FLAGGED)
    assert out["gaps"] == [] and "flagged audit record" in out["dropped"][0]["reason"]


def test_absence_gap_is_kept_when_passages_are_on_topic_and_search_finds_nothing_even_if_a_support_check_would_fail():
    # Regression: a real "no procedure is established" gap was dropped because the old check asked whether passages SUPPORT the description.
    out = run([GAP], FLAGGED, verdict="unsupported")
    assert [g["gap_id"] for g in out["gaps"]] == ["G1"] and out["gaps"][0]["verifier_notes"].startswith("absence supported")


def test_absence_gap_dropped_when_cited_passages_establish_the_thing():
    out = run([GAP], FLAGGED, establishes=True)
    assert out["gaps"] == [] and "absence check failed" in out["dropped"][0]["reason"] and "establish it" in out["dropped"][0]["reason"]


def test_absence_gap_dropped_when_cited_passages_are_off_topic():
    out = run([GAP], FLAGGED, on_topic=False)
    assert out["gaps"] == [] and "not on topic" in out["dropped"][0]["reason"]


def test_absence_gap_dropped_when_a_broader_search_finds_a_provision_that_establishes_it():
    out = run([GAP], FLAGGED, search_establishes=("ae-dl-2-2011-ncema-en-unofficial:art5",))
    assert out["gaps"] == [] and "broader search found" in out["dropped"][0]["reason"]


def test_non_absence_gap_still_needs_supporting_evidence():
    amb = {**GAP, "type": "ambiguous_provision"}
    assert run([amb], FLAGGED)["gaps"][0]["type"] == "ambiguous_provision"
    out = run([amb], FLAGGED, verdict="unsupported")
    assert out["gaps"] == [] and "did not support" in out["dropped"][0]["reason"]


def test_accusatory_wording_dropped_and_lint_catches_it():
    assert wording_problems("The body failed to act and was negligent") and not wording_problems("The provisions do not state who decides")
    out = run([{**GAP, "description": "The operator failed to cancel the alert."}], FLAGGED)
    assert out["gaps"] == [] and "accusatory" in out["dropped"][0]["reason"]


def test_global_comparison_must_be_a_global_source():
    bad = {**GAP, "global_comparison": {"chunk_id": "ae-dl-8-2025-faacd:art4:p1", "why": "x"}}
    out = run([bad], FLAGGED)
    assert out["gaps"][0]["global_comparison"] is None


def test_documentation_limitation_is_not_a_gap():
    recs = [rec("c", [{"flag": "PUBLIC_DOCUMENTATION_LIMITATION", "why": "executive regulation not public"}])]
    out = run([GAP], recs)
    assert out["gaps"] == [] and out["documentation_limitations"][0]["why"].startswith("executive")


def test_render_has_verbatim_claim_closing_line_and_arabic_citation():
    out = run([GAP], FLAGGED)
    out["held_up_well"] = [{"event_id": "E1", "agent": "telecom_operator", "claim": "c", "cited_chunk_ids": ["ae-dl-2-2011-ncema-en-unofficial:art5"], "evidence_status": "partially_supported"}]
    md = render(out, KBStub(), run_id="r", kb_version="kb", models={"agent": "a", "cheap": "c"}, scenario=load_scenario())
    assert CORE_CLAIM in md and CLOSING in md
    assert "Arabic original, authoritative" in md and "non-authoritative" in md and "uaelegislation.gov.ae/ar/legislations/4461" in md  # registry URL, never the English translation
    assert "What held up well" in md and "not policy gaps" in md


def test_render_with_no_gaps_says_so():
    md = render(run([], [rec("a", [])]), KBStub(), run_id="r", kb_version="kb", models={"agent": "a", "cheap": "c"}, scenario=load_scenario())
    assert "No gap met the evidence requirements" in md


# ---------- scorecard ----------
class Chunks:
    def get(self, cid):
        ok = {"ae-dl-2-2011-ncema-en-unofficial:art5", "ae-dl-8-2025-faacd:art4:p1", "ae-dl-8-2025-faacd:art4"}
        return KBStub().get(cid) if cid in KB else ({"text": "t", "metadata": {"doc_id": "x", "article": "a", "title": "t", "url": "u", "translation_status": "original", "authority_status": "current_authoritative"}} if cid in ok else None)


def test_resolve_citation():
    r = KBStub()
    assert scorecard.resolve_citation("Federal Decree-Law No. 2 of 2011, Article 5", r) == ["ae-dl-2-2011-ncema-en-unofficial:art5"]
    assert scorecard.resolve_citation("Totally made up law, Article 9", r) == []
    assert scorecard.resolve_citation("Federal Decree-Law 8/2025 Art. 4", r) == ["ae-dl-8-2025-faacd:art4:p1"]
    assert scorecard.resolve_citation("Decree-Law 8/2025", r) == []  # no article, cannot resolve


def test_score_baseline_counts_unresolvable_citation_as_invalid():
    recs = [{"event_id": "E1", "agent": "baseline:emergency_management", "claims": [
        {"text": "x issues alerts", "claim_type": "mandate", "citation_text": "Decree-Law 2/2011 Art. 99"},
        {"text": "y coordinates", "claim_type": "mandate", "citation_text": "Decree-Law 8/2025 Art. 4"}]}]
    s = scorecard.score_baseline(recs, KBStub(), llm([]), "v")
    assert s["claims"] == 2 and s["valid"] == 1 and s["unsupported_mandate_claims_surviving"] == 1


def test_score_grounded_reads_gate_outcomes():
    recs = [{"event_id": "E1", "agent": "a", "claims": [
        {"text": "No published mandate located in the available knowledge base.", "original_text": "NCEMA cancels", "claim_type": "mandate", "cited_chunk_ids": [], "verifier_status": "unsupported"},
        {"text": "ok", "claim_type": "mandate", "cited_chunk_ids": ["c"], "verifier_status": "supported"}]}]
    s = scorecard.score_grounded(recs)
    assert (s["claims"], s["valid"], s["mandate_claims_rejected_by_gate"], s["unsupported_mandate_claims_surviving"]) == (2, 1, 1, 0)


def test_spot_check_csv_is_seeded_and_blank_for_humans(tmp_path):
    rows = [{"condition": c, "event": "E1", "agent": "a", "type": "fact", "claim": f"{c}{i}", "citation": "x", "verifier": "pass"} for c in ("grounded", "baseline") for i in range(30)]
    scorecard.spot_check_csv(rows, tmp_path / "s.csv")
    scorecard.spot_check_csv(rows, tmp_path / "t.csv")
    a, b = (tmp_path / "s.csv").read_text(), (tmp_path / "t.csv").read_text()
    assert a == b and len(a.splitlines()) == 21 and ",," in a


# ---------- after the first live run ----------
def test_report_dedupes_held_up_and_limitations_and_caps_hash_lists():
    out = run([{**GAP, "source_records": ["a" * 12]}], FLAGGED)
    out["held_up_well"] = [{"event_id": f"E{i % 6 + 1}", "agent": "telecom_operator", "claim": "Licensee must comply with directions.",
                            "cited_chunk_ids": ["ae-dl-8-2025-faacd:art4:p1"], "evidence_status": "confirmed"} for i in range(60)]
    out["held_up_well"] += [{"event_id": "E1", "agent": "telecom_operator", "claim": f"Distinct claim {i}", "cited_chunk_ids": [],
                             "evidence_status": "partially_supported"} for i in range(30)]
    out["documentation_limitations"] = [{"record": "x", "event_id": "E1", "agent": "emergency_management", "why": "Executive Regulation is not public."}] * 22
    out["gaps"][0]["source_records"] = [chr(97 + i) * 64 for i in range(10)]
    md = render(out, KBStub(), run_id="r", kb_version="kb", models={"agent": "a", "cheap": "c"}, scenario=load_scenario())
    assert md.count("Licensee must comply with directions.") == 1
    assert md.count("Distinct claim") <= 13 and "90 claims passed" in md
    assert md.count("Executive Regulation is not public.") == 1 and "Raised 22 times" in md
    assert "(+7 more)" in md and len(md) < 20000


def test_gap_label_reflects_unofficial_translation_cap():
    from report.render import _gap_label

    on_translation = {**GAP, "evidence": [{"chunk_id": "ae-dl-2-2011-ncema-en-unofficial:art5"}]}
    on_official = {**GAP, "evidence": [{"chunk_id": "ae-dl-8-2025-faacd:art4:p1"}]}
    assert _gap_label(KBStub(), on_translation).startswith("partially_supported")
    assert _gap_label(KBStub(), on_official).startswith("confirmed")


def test_resolver_handles_eu_directive_but_not_unknown_foreign_law():
    r = KBStub()
    KB["eu-eecc-2018-1972:art110"] = ("Member States shall ensure that public warnings are transmitted.",
        {"doc_id": "eu-eecc-2018-1972", "article": "Art. 110", "title": "t", "url": "https://u/eu", "translation_status": "original", "authority_status": "reference_global"})
    try:
        assert scorecard.resolve_citation("Directive (EU) 2018/1972, Article 110(1)", r) == ["eu-eecc-2018-1972:art110"]
        assert scorecard.resolve_citation("Emergency Management Act, S.C. 2007, c. 15, section 4(1)", r) == []
    finally:
        del KB["eu-eecc-2018-1972:art110"]


def test_both_conditions_get_the_same_jurisdiction_information():
    from agents.profiles import PROFILES
    from scenario.engine import BASELINE_SYSTEM

    for p in PROFILES.values():
        assert "United Arab Emirates (federal level)" in p.system_prompt()
    assert "United Arab Emirates (federal level)" in BASELINE_SYSTEM
    assert "scenario itself belong in reasoning_summary" in BASELINE_SYSTEM  # same claims-only rule as the grounded agents


def test_scorecard_reports_mandate_validity_separately():
    recs = [{"event_id": "E1", "agent": "a", "claims": [
        {"text": "x", "claim_type": "fact", "cited_chunk_ids": ["c"], "verifier_status": "supported"},
        {"text": "y", "claim_type": "mandate", "cited_chunk_ids": ["c"], "verifier_status": "supported"},
        {"text": "No published mandate located in the available knowledge base.", "original_text": "z", "claim_type": "mandate", "cited_chunk_ids": [], "verifier_status": "unsupported"}]}]
    s = scorecard.score_grounded(recs)
    assert (s["claims"], s["valid"], s["mandate_claims_proposed"], s["mandate_valid"]) == (3, 2, 2, 1)


def test_baseline_token_budget_is_large_enough_for_reasoning_models():
    import yaml
    from pathlib import Path

    cfg = yaml.safe_load((Path(__file__).resolve().parents[1] / "config.yaml").read_text())
    assert cfg["llm"]["max_tokens"] >= 8000  # two baseline answers were truncated at 4000 and lost


def test_baseline_claims_fall_into_exactly_one_bucket_and_uncited_is_not_counted_as_a_bad_citation():
    recs = [{"event_id": "E1", "agent": "baseline:x", "claims": [
        {"text": "a", "claim_type": "mandate", "citation_text": "Federal Decree-Law 8/2025, Article 4"},
        {"text": "b", "claim_type": "mandate", "citation_text": "No specific UAE federal provision known to this agent"},
        {"text": "c", "claim_type": "mandate", "citation_text": ""},
        {"text": "d", "claim_type": "comparison", "citation_text": "OASIS CAP 1.2, Section 3.2.1"},
        {"text": "e", "claim_type": "fact", "citation_text": "Decree-Law 8/2025 Art. 4"}]}]

    def llm_by_text(prompt, *, system="", model=None, max_tokens=None, purpose="", use_cache=True):
        v = "unsupported" if "CLAIM (fact): e" in prompt else "supported"
        return SimpleNamespace(text=json.dumps({"verdict": v, "coordination_only": False, "rationale": "r"}))

    s = scorecard.score_baseline(recs, KBStub(), llm_by_text, "v")
    assert sum(s["buckets"].values()) == s["claims"] == 5
    assert s["buckets"] == {"valid": 1, "resolved_unsupported": 1, "cited_not_in_kb": 1, "uncited": 2}
    assert s["cited_claims"] == 3 and s["validity_pct_of_cited"] == 33.3


def test_uncited_detector_handles_blank_and_admissions_but_not_real_citations():
    u = scorecard.UNCITED
    assert all(u.search(t) for t in ["", "   ", "Provision not known", "No specific UAE provision known"])
    assert not any(u.search(t) for t in ["Federal Decree-Law No. 2 of 2011, Article 5", "OASIS CAP 1.2, Section 3.2.1"])
