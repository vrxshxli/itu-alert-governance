# Demo video script (max 7 min, screen recording of the viewer + short voice-over)

Record the live viewer (or `python scripts/serve_viewer.py`). Say only what is on screen. Do not describe any institution's real behaviour.

| Time | Screen | Say |
|---|---|---|
| 0:00 to 0:30 | Title slide / README top | "This project does not assess UAE institutions. It tests whether a published-policy knowledge base enables accountable, evidence-grounded coordination during a hypothetical public-alert governance failure. The scenario is fictional." |
| 0:30 to 1:30 | Viewer: timeline of E1 to E6 | "Six fictional events in the district of Northvale: an unexplained emergency-labelled cell broadcast, public questions, a configuration fault, journalists asking who corrects it. Three agents (telecom operator, emergency management, policy adviser) each see only their own inbox." |
| 1:30 to 3:00 | Click one record: claims, citation chips, verifier status | "Every claim cites a passage from the knowledge base. A second model checks the passage supports the claim. A claim without support is rejected. Claims that rest on the unofficial English translation of the NCEMA law are capped at partially supported; the Arabic original is the authority." |
| 3:00 to 4:00 | Flags and audit record, hash | "Where sources do not name an owner, the agent flags it instead of guessing. Every record is appended to a hash-chained audit log. Agents only propose actions; a named human approves or rejects." |
| 4:00 to 5:00 | Scorecard tab | "Same scenario, same inbox, plain LLM without the knowledge base. Mandate claims passing verification: 4 of 16 plain, 86 of 91 grounded. Both flagged all four not-established topics, so the gain is checkable citations, not abstention. One run per condition; no significance claimed; the same model family verifies, so we added a human spot check of 20 claims: [RESULT]." |
| 5:00 to 6:30 | Gap report: G1, G2, G4, then G3/G5 labelled lower-confidence | "Three gaps, each tied to evidence: no event-specific decision owner named in the published sources; no published procedure for correcting a delivered alert; no verification channel for municipal offices. These say what the documents establish, not how anyone behaves. The Executive Regulation is not in the public corpus, which we list as a documentation limitation." |
| 6:30 to 7:00 | Closing slide | "The system does not decide who is right. It shows what the published evidence supports, what it does not establish, and where human authority is required." |

Checklist before recording: viewer shows run `run-20261108-200619-f7608f8d`; spot-check result filled in; no API key or terminal history visible.
