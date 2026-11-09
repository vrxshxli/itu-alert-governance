# Scorecard: plain LLM vs KB-grounded (run `run-20261108-200619-f7608f8d`)

Same scenario, same roles, same inbox visibility, same verifier model against the same KB. One run per condition: these are counts from a single run, not a statistical comparison, and we claim no significance. Information parity: both conditions are told the jurisdiction (UAE, federal) and the same rule that claims concern published rules only; the baseline has a larger output budget (12,000 vs 8,000 tokens) because two of its answers were cut off at 4,000 in an earlier attempt.

| Metric | Plain LLM (no KB) | KB-grounded |
|---|---|---|
| Claims made | 28 | 151 |
| Citation validity, strict (every claim counts; a claim with no specific provision counts as not valid) | 9/28 (32.1%) | 146/151 (96.7%) |
| Citation validity among claims that name a specific provision | 9/16 (56.2%) | 146/151 (96.7%) |
| Mandate claims proposed | 16 | 91 |
| Mandate claims that pass (the claims that matter most; factual claims about passages are easier to get right) | 4/16 | 86/91 |
| Mandate claims rejected by the evidence gate/verifier | n/a (no gate) | 5 |
| Unsupported mandate claims that remain in the output | 12 | 0 |
| Missing mandates correctly flagged (of 4 topics the read sources do not establish) | 4 | 4 |
| Verifiable gaps (gap report entries whose evidence the verifier supports) | 0 (no chunk-linked evidence exists, by construction) | 5 |

## Why plain-LLM claims were not counted valid

| Bucket | Claims | Meaning |
|---|---|---|
| valid | 9 | resolves to a KB chunk and the verifier says it supports the claim |
| resolved_unsupported | 5 | resolves to a KB chunk, but the chunk does not support the claim (or, for a mandate, cannot ground one) |
| cited_not_in_kb | 2 | names a provision we cannot map to a KB chunk (a different law, no article number, or a source outside the KB): not checkable here, not proven wrong |
| uncited | 12 | names no specific provision (for example 'No specific UAE provision known'): an honest admission, but a mandate asserted this way is unsupported |

## Topics the sources do not establish, per run

| Topic | Plain LLM | Grounded |
|---|---|---|
| T1 which body issues or authorises a public alert | flagged: True, asserts an answer: False | flagged: True, asserts an answer: False |
| T2 which body cancels or corrects an alert that was already delivered, and how | flagged: True, asserts an answer: False | flagged: True, asserts an answer: False |
| T3 which authority is the 'competent authority' that directs an operator in a public emergency | flagged: True, asserts an answer: False | flagged: True, asserts an answer: False |
| T4 the content of the Executive Regulation that sets event classification and each body's role | flagged: True, asserts an answer: False | flagged: True, asserts an answer: False |

The topic judgements above are made by the verifier model; check them in `report/spot_check.csv` workflow before relying on them.

## Manual spot check

`report/spot_check.csv` holds a seeded sample of about 20 claims (half per condition). Fill the `human_verdict` column (supported / partly / unsupported) against the cited passage and record the totals here before submission:

_Human spot-check result: not yet done._
