"""Gap analysis, gap report and scorecard from a finished run.   python scripts/make_report.py [run_id]

Outputs (report/): gap_analysis.json, gap_report.md, scorecard.md, spot_check.csv (fill in `human_verdict`: ~20 claims).
Needs the built KB, embedding model and OPENAI_API_KEY (cached calls are free on re-run).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents import approvals  # noqa: E402
from agents.audit import verify_chain  # noqa: E402
from agents.gap_analyst import analyse  # noqa: E402
from agents.llm import CONFIG, call_llm  # noqa: E402
from kb.embedder import get_embedder  # noqa: E402
from kb.retrieval import Retriever  # noqa: E402
from report.render import render, write  # noqa: E402
from scenario.engine import load_scenario  # noqa: E402
from scenario.scorecard import missing_flagged, score_baseline, score_grounded, spot_check_csv  # noqa: E402

RUNS = ROOT / "audit" / "runs"


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main(argv: list[str]) -> int:
    run_id = argv[0] if argv else sorted(p.name[:-len(".manifest.json")] for p in RUNS.glob("*.manifest.json"))[-1]
    g_path, b_path = RUNS / f"{run_id}.jsonl", RUNS / f"{run_id}.baseline.jsonl"
    for p in (g_path, b_path):
        ok, msg = verify_chain(p)
        print(f"{p.name}: {msg}")
        if not ok:
            return 1
    grounded, baseline = load(g_path), load(b_path)
    r = Retriever(get_embedder())
    m, cheap = CONFIG["models"]["agent"], CONFIG["models"]["cheap"]

    analysis = analyse(grounded, r, call_llm, model=m, verifier_model=cheap)
    (ROOT / "report" / "gap_analysis.json").write_text(json.dumps(analysis, indent=1, ensure_ascii=False), encoding="utf-8")
    decided = {d["record_hash"]: d["decision"] for d in approvals._read(run_id)}
    appr = {"approved": sum(v == "approved" for v in decided.values()), "rejected": sum(v == "rejected" for v in decided.values())}
    appr["pending"] = len(approvals.pending(run_id)) if g_path.exists() else 0
    write(ROOT / "report" / "gap_report.md", render(analysis, r, run_id=run_id, kb_version=CONFIG["kb"]["version"], models=CONFIG["models"],
                                                    scenario=load_scenario(), approvals=appr, scorecard_path="report/scorecard.md"))

    sg, sb = score_grounded(grounded), score_baseline(baseline, r, call_llm, cheap)
    mg, mb = missing_flagged(grounded, call_llm, cheap), missing_flagged(baseline, call_llm, cheap)
    spot_check_csv(sg["rows"] + sb["rows"], ROOT / "report" / "spot_check.csv")
    L = [f"# Scorecard: plain LLM vs KB-grounded (run `{run_id}`)", "",
         "Same scenario, same roles, same inbox visibility, same verifier model against the same KB. One run per condition: these are "
         "counts from a single run, not a statistical comparison, and we claim no significance. Information parity: both conditions are told the jurisdiction "
         "(UAE, federal) and the same rule that claims concern published rules only; the baseline has a larger output budget (12,000 vs 8,000 tokens) "
         "because two of its answers were cut off at 4,000 in an earlier attempt.", "",
         "| Metric | Plain LLM (no KB) | KB-grounded |", "|---|---|---|",
         f"| Claims made | {sb['claims']} | {sg['claims']} |",
         f"| Citation validity, strict (every claim counts; a claim with no specific provision counts as not valid) | {sb['valid']}/{sb['claims']} ({sb['validity_pct']}%) | {sg['valid']}/{sg['claims']} ({sg['validity_pct']}%) |",
         f"| Citation validity among claims that name a specific provision | {sb['valid']}/{sb['cited_claims']} ({sb['validity_pct_of_cited']}%) | {sg['valid']}/{sg['claims']} ({sg['validity_pct']}%) |",
         f"| Mandate claims proposed | {sb['mandate_claims_proposed']} | {sg['mandate_claims_proposed']} |",
         f"| Mandate claims that pass (the claims that matter most; factual claims about passages are easier to get right) | {sb['mandate_valid']}/{sb['mandate_claims_proposed']} | {sg['mandate_valid']}/{sg['mandate_claims_proposed']} |",
         f"| Mandate claims rejected by the evidence gate/verifier | n/a (no gate) | {sg['mandate_claims_rejected_by_gate']} |",
         f"| Unsupported mandate claims that remain in the output | {sb['unsupported_mandate_claims_surviving']} | {sg['unsupported_mandate_claims_surviving']} |",
         f"| Missing mandates correctly flagged (of {mg['of']} topics the read sources do not establish) | {mb['correctly_flagged']} | {mg['correctly_flagged']} |",
         f"| Verifiable gaps (gap report entries whose evidence the verifier supports) | 0 (no chunk-linked evidence exists, by construction) | {len(analysis['gaps'])} |",
         "", "## Why plain-LLM claims were not counted valid", "",
         "| Bucket | Claims | Meaning |", "|---|---|---|",
         f"| valid | {sb['buckets']['valid']} | resolves to a KB chunk and the verifier says it supports the claim |",
         f"| resolved_unsupported | {sb['buckets']['resolved_unsupported']} | resolves to a KB chunk, but the chunk does not support the claim (or, for a mandate, cannot ground one) |",
         f"| cited_not_in_kb | {sb['buckets']['cited_not_in_kb']} | names a provision we cannot map to a KB chunk (a different law, no article number, or a source outside the KB): not checkable here, not proven wrong |",
         f"| uncited | {sb['buckets']['uncited']} | names no specific provision (for example 'No specific UAE provision known'): an honest admission, but a mandate asserted this way is unsupported |",
         "", "## Topics the sources do not establish, per run", "", "| Topic | Plain LLM | Grounded |", "|---|---|---|"]
    for tid, t in mg["topics"].items():
        b = mb["topics"][tid]
        L.append(f"| {tid} {t['topic']} | flagged: {b.get('flagged_as_not_established')}, asserts an answer: {b.get('asserts_an_answer')} | "
                 f"flagged: {t.get('flagged_as_not_established')}, asserts an answer: {t.get('asserts_an_answer')} |")
    L += ["", "The topic judgements above are made by the verifier model; check them in `report/spot_check.csv` workflow before relying on them.",
          "", "## Manual spot check", "", "`report/spot_check.csv` holds a seeded sample of about 20 claims (half per condition). Fill the `human_verdict` "
          "column (supported / partly / unsupported) against the cited passage and record the totals here before submission:", "",
          "_Human spot-check result: not yet done._", ""]
    write(ROOT / "report" / "scorecard.md", "\n".join(L))
    print("wrote report/gap_report.md, report/scorecard.md, report/spot_check.csv")
    print(f"gaps={len(analysis['gaps'])} dropped={len(analysis['dropped'])} limitations={len(analysis['documentation_limitations'])} held_up={len(analysis['held_up_well'])}")
    print(f"validity: baseline {sb['validity_pct']}%  grounded {sg['validity_pct']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
