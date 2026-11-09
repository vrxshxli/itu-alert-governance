# Handoff: what is done, what is left

Project: Alert Governance Stress-Test (ITU AI for Good Lab Hackathon, UAE). Deadline 10 Nov 2026, email to aiforgoodlab@itu.int (confirm the time zone with the organisers).
Core claim (keep verbatim everywhere): "This project does not assess UAE institutions. It tests whether a published-policy knowledge base enables accountable, evidence-grounded coordination during a hypothetical public-alert governance failure."

## Start here
1. Read `README.md`, then `docs/FRONTEND_OVERVIEW.md` (frontend), `docs/CHANGELOG_DECISIONS.md` (changes made after seeing results), `submission/CHECKLIST.md`.
2. Open `docs/index.html` in a browser. That is the finished viewer (4 tabs, read-only, no server, no key).
3. Run the tests (no key, no network): `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python -m pytest -q tests` (81 should pass).

## Done (do not redo)
- Knowledge base, agents, evidence gate, verifier, audit log, approval gate, scenario, plain-AI baseline, gap report, scorecard (final run: `run-20261108-200619-f7608f8d`).
- Technical report draft: `submission/technical_report.pdf` and `.docx` (3 pages).
- Viewer, README, demo video script, submission email text.

## Please do NOT
- Do not run `scripts/run_scenario.py` again. It spends API money and creates a new run id, so the report, scorecard and viewer would no longer match. Results come from one final run.
- Do not put any API key in the repo, the chat, or a shared zip. You do not need a key for anything below.
- Do not add UAE source text (PDFs, extracted text, KB export) to the repo. `kb/raw`, `kb/text`, `kb/export` stay git-ignored.
- Do not use the words "live", "attack", "real incident" or military imagery in the UI. The scenario is fictional.
- Do not edit the audit logs in `audit/runs/` (hash-chained; any edit breaks the chain).

## Left to do (needs a person)
1. **Fill placeholders** (search for square brackets): team name and members, repo URL, live URL, video URL, spot-check result. Files: `submission/technical_report.docx` (rebuild PDF after), `README.md`, `submission/submission_email.md`, `submission/demo_video_script.md`.
2. **Human spot check:** open `report/spot_check.csv`, fill `human_verdict` for the ~20 claims (supported / partly / unsupported) against the cited passages, then record the totals in the report and in `report/scorecard.md`.
3. **Approve or reject the pending proposals (22)**, or decide not to: `python scripts/serve_viewer.py` then use the buttons under "What happened" > Technical evidence. A named human is asked for a name. Decisions are permanent.
4. **Git:** set a real identity (`git config user.name`, `git config user.email`), rewrite old commits if wanted (`git rebase -r --root --exec 'git commit --amend --no-edit --reset-author'`), run the safety checks (`git ls-files kb/raw kb/text kb/export .env models` must print nothing), create a PUBLIC GitHub repo, push, then Settings > Pages > Deploy from branch `main`, folder `/docs`.
5. **Demo video** (max 7 min) from `submission/demo_video_script.md`.
6. **Email the organisers** (`submission/submission_email.md`): ask whether a local KB export is acceptable and the deadline time zone.
7. **Optional:** verify NCEMA citations against the Arabic original; check the viewer on a wide screen and a phone.

## If you change the frontend
- Edit only `viewer/index.html`, then: `python scripts/export_viewer.py && cp report/viewer_export.html docs/index.html && python -m pytest -q tests`.
- Keep the first line of the main script (`<script>` followed by `const EXPORT`): the export script finds it by that exact text.
- Keep: FICTIONAL SIMULATION label, the core claim, citation drawer, named-human approval, audit chain indicator, and the three evidence labels (confirmed / partially_supported / not_established_from_public_sources) in detail views.
