# Submission checklist (deadline 10 Nov 2026, aiforgoodlab@itu.int)

Confirm the deadline time zone and any extension with the organisers.

## Deliverables

- [x] Technical report draft, 3 pages, sections (a) to (h) (`submission/technical_report.pdf` + `.docx`); fill team, repo URL, spot-check result
- [ ] Public GitHub repository link (code, `kb/sources.md`, `kb/sources.yaml`, scripts, licences, disclaimer)
- [ ] KB: `kb/sources.md` (always) + ITU KB export (**pending organiser confirmation**, see below)
- [ ] Demo video (optional unless shortlisted; max 7 min)
- [ ] Team name and member details
- [x] Email text prepared (`submission/submission_email.md`); video script in `submission/demo_video_script.md`

## Data constraints (must hold before anything is published or sent)

- [ ] **No copyrighted UAE source text in the public repo.** `git ls-files kb/raw kb/text kb/export` returns nothing;
      `grep` of the repo for long passages from UAE legislation returns nothing.
- [ ] **ITU KB export held back until the organisers confirm** that a local export is acceptable and on what terms
      (contains chunk text from sources whose publishers reserve all rights). Record their reply here:
      _confirmation: pending_.
- [ ] Every NCEMA citation shows the Arabic source URL and article; English renderings are labelled
      "unofficial translation, non-authoritative".
- [ ] Repealed Decree-Law 35/2024 appears only as labelled historical context, never as current authority.
- [ ] `.env` and `models/` are not in git history (`git log --all -- .env models` is empty).
- [ ] Git author identity is the team's (not the placeholder used for early commits).

## Questions for the organisers

1. Is a local KB export (JSONL chunks + metadata) acceptable, or must the KB be ingested into the AI for Good Lab
   environment? May it contain text from sources whose publishers reserve all rights?
2. Deadline time zone and any extension.
3. API budget or sandbox credits available.
