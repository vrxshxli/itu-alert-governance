# Decisions changed after seeing results

Recorded for disclosure in the report. Each change was made after looking at run output, so it is not a pre-registered choice.

1. **Fair baseline.** First baseline run scored 0.0% valid. Causes were on our side: the baseline was not told the jurisdiction, two answers were truncated at 4,000 output tokens, and EU citations could not be resolved. We gave the baseline the jurisdiction line and the claims-only rule, raised its output budget to 12,000 (grounded: 8,000), and added an EU citation resolver. Result: baseline 32.1% strict validity, grounded 96.7%.
2. **Baseline buckets.** Honest abstentions ("no specific provision known") were being counted as bad citations. Every baseline claim now falls in exactly one bucket (uncited, cited_not_in_kb, resolved_unsupported, valid). The report shows strict validity and validity among cited claims.
3. **Absence gate for gaps.** The gap analyst dropped a real "no correction procedure is established" gap, because the verifier tested whether passages *support* an absence. Absence-type gaps now pass if the cited passages are on topic and do not establish the thing, and a broader current-law search finds no provision that does. `ambiguous_provision` keeps the support check. This makes the gate stricter on one side (broader search) and looser on the other (no support requirement); we disclose both.
4. **Repeated runs.** The scenario was run more than once while fixing 1 to 3. Results are from a single final run per condition; no significance is claimed.
5. **Same-family verifier.** The verifier and scorer are from the same model family as the agents. The 20-claim human spot check (`report/spot_check.csv`) is the independent check.
