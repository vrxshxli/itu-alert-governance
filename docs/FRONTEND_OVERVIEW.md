# Frontend overview (for an outside reviewer / LLM)

Paste this file, then `viewer/index.html`, into the chat and ask for design or code suggestions.

## What the product is
"Alert Governance Stress-Test": institutions are modelled as AI agents (Emergency Management, Telecom Operator, Policy Adviser) in a **fictional** false-public-alert scenario (district "Northvale", events E1 to E6). A knowledge base of officially published documents grounds the agents' claims; a verifier checks each claim; a hash-chained audit log records everything; a human must approve any proposed action. A gap report lists what the published sources do not establish. A plain LLM without the KB runs as a baseline.

The frontend only **displays a finished, recorded run**. It makes no model calls and has no business logic about scores or evidence.

## Files
| File | Role |
|---|---|
| `viewer/index.html` | The whole UI: one file, inline CSS + vanilla JS, no framework, no build step, no external assets |
| `viewer/server.py`, `viewer/data.py` | Local stdlib HTTP server (127.0.0.1 only) that serves the JSON API below. Backend: do not change |
| `scripts/serve_viewer.py` | One command to start the local viewer (port 8765) |
| `scripts/export_viewer.py` | Bakes run data into `viewer/index.html` as `window.__EXPORT__` and writes a single static file `report/viewer_export.html` (copied to `docs/index.html` for GitHub Pages) |

The page runs in two modes from the same file:
- **Local viewer** (`LIVE = !window.__EXPORT__`): fetches `/api/runs`, `/api/run/<id>`, `/api/report`, `/api/chunk/<id>`; shows Approve/Reject buttons (POST `/api/approve`, needs a reviewer name).
- **Read-only export**: same functions read from `window.__EXPORT__` (`api()` is the single data switch). No server, no key, no approve buttons. The export contains source citations only, never source passage text (publisher copyright).
The export script injects data by string-replacing the exact text `<script>\nconst EXPORT` at the start of the main script. Keep that line unchanged.

## Data contract (do not change)
- `run`: `run_id`, `manifest` (models, kb_version, record counts), `scenario.events[]` (`event_id`, `t_offset` minutes, `visible_to[]`, `content`, `uncertainty`), `grounded[]` and `baseline[]` audit records, `approvals{hash: {decision, by}}`, `chain{grounded,baseline: {ok,message}}`, `flag_meaning{}`.
- A grounded record: `event_id` (follow-ups look like `E1+followup`), `agent`, `inputs_seen[]`, `reasoning_summary`, `claims[]` (`text`, `claim_type`, `cited_chunk_ids[]`, `evidence_status` confirmed|partially_supported|not_established_from_public_sources, `verifier_status`, optional `original_text` when a claim was rewritten), `flags[]` (`flag`, `why`), `recommended_action` (`action`, `detail`, `human_authority_needed`), `human_approval.required`, `messages_sent[]`, `hash`, `prev_hash`.
- `report`: `gap_report` (markdown), `scorecard` (markdown), `gap_analysis` (`gaps[]` with `gap_id`, `type`, `description`, `evidence[{chunk_id, why}]`, `severity{level, rationale}`, `affected_institutions`, `direction`, `global_comparison`, `verifier_notes`, `source_records`; plus `documentation_limitations[]`).
- Scorecard numbers are **parsed from the scorecard markdown table** (`parseScore`), never hardcoded.

## Views: four tabs, one guided story (left rail on desktop, top bar under 900px)
Default screens show only plain-language answers. Everything technical (raw logs, hashes, claim ids, verifier labels, raw flag names, long reasoning, full citations, source detail, the approval buttons, the audit feed, the plain-AI answers) sits behind one `Technical evidence` drawer per page (`tech(tab, inner)`); its open state is remembered so filters and approvals do not collapse it.
1. **Overview** (`renderOverview`) — "What is this test?" Exact pitch ("When a public alert may be wrong, who can act? ..."), FICTIONAL SIMULATION tag, a faded text-free map graphic (`heroSVG`), three blocks (Problem, Method, Result; the Result numbers come from the run data), two buttons, the compact neutral disclaimer, closing line. Technical evidence holds the labelled simulation map, the 4-step flow, the simulated resident phone (drawing only, nothing is sent), run details, methodology, caveats and audit integrity.
2. **What happened** (`renderTimeline`) — "The six-event replay". "Event N of 6", Previous/Next/Replay, time track; one event at a time: what happened (first sentence), who received it, recommended next step per role, whether human review is needed. Technical evidence holds the full event text, what is uncertain, and the agent cards (with Approve/Reject in the local viewer, claims, citations, raw flags, hashes).
3. **What we found** (`renderGaps`) — "Evidence-supported findings". The three main findings only: severity, plain title, why it matters, what the documents do not say, and a `View evidence` drawer with the cited sources. Technical evidence holds the lower-confidence observations (`LOWER_CONFIDENCE`), source limitation, the NCEMA translation caveat and the full gap report.
4. **Results & audit** (`renderScore`) — "AI with vs without documents". Core comparison (146/151 vs 9/28 verified, parsed from the scorecard), one-run caveat, audit chain status in one sentence. Technical evidence holds the other metrics, how it was measured, the full scorecard, the filterable audit feed with hashes, and the plain-AI answers.
Readable-label maps (`FLAG_LABEL`, `ACTION_LABEL`, `evShort`) are presentation only; raw names and the three evidence labels remain in detail views.
Clicking any citation chip (mouse or Enter) opens a right-hand drawer (`openChunk`) with the citation, authority status, translation status and a link to the official source.

## Visual system
Dark base (#04070e, midnight navy), glass panels (translucent gradient, blur, thin luminous border), cyan = verified evidence, amber = uncertainty / human approval, restrained red and green for status only, violet for flags. System sans font; monospace for ids. Atmosphere: CSS grid, scan lines, low-opacity canvas particles. Transitions 200 to 500 ms. `prefers-reduced-motion` disables all animation and the particle motion.

## Hard constraints (please respect in any suggestion)
- Must stay a single self-contained file: local CSS/SVG only, no external images, fonts, CDNs or paid assets.
- Do not change the data contract, scores, evidence text, labels (confirmed / partially_supported / not_established_from_public_sources) or the disclaimers.
- The core claim must stay visible: "This project does not assess UAE institutions. It tests whether a published-policy knowledge base enables accountable, evidence-grounded coordination during a hypothetical public-alert governance failure."
- Never imply real UAE operations, real locations or real incidents. Avoid the words "live", "attack", "real incident", and military/defence imagery. The map is a neutral outline; Northvale is fictional.
- Auditability features (hash display, chain status, approve/reject with a named human, citation drawer) must remain.
- The app must work from a static file opened over `file://` or GitHub Pages.

## Known limitations / things worth asking about
- Visually checked: Overview at mobile width and at a 1360px desktop width (scaled iframe). Timeline, Gaps, Scorecard, Audit were checked with a scripted DOM test and earlier visual passes, not re-screenshotted after the latest simplification.
- The outline is a hand-drawn abstract polygon; it only loosely suggests a coastline.
- The three view bodies are rebuilt via `innerHTML` on every state change (simple, but no diffing); the playhead animation relies on a double `requestAnimationFrame` after render.
- No keyboard navigation inside the timeline track beyond tab focus on the event buttons; accessibility has had only basic attention (aria-labels on SVG and event buttons, Escape closes the drawer).
- The scorecard table can get cramped under ~500px.
- Ideas welcome: stronger information hierarchy on the Overview, better empty/loading states, contrast checks, mobile layout, microcopy, how to present "human approval required" more prominently without implying live operations.
