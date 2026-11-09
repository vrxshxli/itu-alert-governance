# Source-authority and mandate-safety rules

These rules bind retrieval, agent prompts, the verifier and the report. Code: `kb/authority.py` (tested in
`tests/test_authority.py`). Registry: `kb/sources.yaml`.

## R1. Arabic NCEMA source is authoritative; English is an unofficial translation
- Federal Decree-Law No. (2) of 2011 (`ae-dl-2-2011-ncema`) is published officially in Arabic only. The Arabic PDF is the
  authoritative source.
- Any English rendering is stored as `ae-dl-2-2011-ncema-en-unofficial`, `translation_status: unofficial_translation`.
- Every retrieval result and report citation from this law shows the **Arabic source URL and Arabic article number**.
  English text is shown only with the label "unofficial translation, non-authoritative".
- A mandate claim supported **only** by the translated text is capped at `partially_supported`, never `confirmed`.

## R2. No mandate by inference from coordination clauses
- "In coordination with NCEMA" (e.g. Decree by Law No. (8) of 2025, Art. (4)(5)) establishes a **coordination
  relationship only**. It must never be used as evidence that NCEMA owns, operates, triggers, authorises or cancels
  national alerts.
- More generally, an institution's power to perform an action is established only by a provision that **assigns that
  action to that institution**. Coordination, consultation, being informed, or being named in a preamble does not
  establish the power.
- If no such provision is retrieved, the agent logs `NO_MANDATE_FOUND`. After the second, broader retrieval and source
  check (brief 14.4), it becomes `PUBLIC_DOCUMENTATION_LIMITATION`.

## R3. Role mandate profiles are built only from directly verified articles
- Before any role mandate profile is created, each article it cites is read in the official source (Arabic PDF for
  NCEMA) and recorded in `articles_verified` in `kb/sources.yaml`, with the date checked.
- The Emergency Management agent's allowed actions are limited to what verified articles explicitly establish. Anything
  else is "recommend to a human" or "request coordination", never "decide" or "execute".

## R4. Repealed law is historical context only
- `ae-dl-35-2024-cda` (`historical_repealed`) is excluded from every current-authority retrieval. It may be retrieved only
  through the explicit history mode, and its citations carry "REPEALED by Decree by Law No. (8) of 2025, Art. (19)".
- Claims supported only by a repealed source cannot be labelled `confirmed` or `partially_supported` for current
  authority.

## R5. Currency is always shown
- The 2003 telecom law is kept with its currency note (portal "last update" 27 Sep 2020, 3 amendments, some pre-2008
  terminology in the English text).
- Current operator obligations are taken from the TDRA public licence No. (3) of 2026 (effective 09 Aug 2026), Art. 8
  (public emergencies, public interest/safety/national security) and Art. 12.4 (resilience). It binds the named licensee;
  the other licensee's licence is not verified, so claims must not generalise to "all operators".
- TDRA TS FS 001 and the UAE-Alert table are technical standards: they support technical facts (alert classes, channel
  IDs, bilingual display, no user opt-out for national alerts) but **not** who originates, authorises or cancels an alert.

## R6. Global sources are comparisons, not UAE mandates
`reference_global` sources (FCC, EU EECC) and ITU standards may appear only in `global_comparison` fields and in the
Policy Adviser's comparative statements, never as the basis of a UAE institution's mandate.

## Articles verified so far (read directly in the official source)

| Source | Article | What it says (paraphrase) | What it does NOT establish |
|---|---|---|---|
| Decree by Law 8/2025 (EN official translation) | Art. (2)(1)-(2) | Establishes the Federal Authority for Ambulance and Civil Defense, reporting to the Cabinet; it supersedes the Civil Defense Authority under Decree-Law 35/2024 | Anything about NCEMA's own powers |
| Decree by Law 8/2025 | Art. (4)(5) | The Authority's competence: "Establish a public warning system for the population against potential hazards, in coordination with" NCEMA | That NCEMA owns, operates, triggers, authorises or cancels alerts; who issues individual alerts |
| Decree by Law 8/2025 | Art. (19)(1) | Repeals Decree-Law 35/2024 | n/a |
| Decree by Law 8/2025 | Art. (20) | In force 01 Jan 2026 | n/a |
| TDRA Licence 3/2026 | Art. 8.1 | If a competent authority declares a public emergency, the licensee complies with directions of TDRA or other competent authority regarding its property, use or operation | Which authority is "competent" for public warnings; any cell-broadcast-specific duty |
| TDRA Licence 3/2026 | Art. 8.2, 8.3 | Compliance with directions on public interest, safety, national security; assumption of control on written direction | Same as above |
| TDRA TS FS 001 v2.0 | §2, §4.2 | UAE-Alert uses cell broadcast "to disseminate warning alerts issued by authorities"; handsets show Arabic and English; no reply/forward/copy; display without user interaction | Identity of the "Alert Originator"; cancellation procedure |
| Data protection law 45/2021 | Art. (2)(2)(a)-(b) | The law does not apply to Government Data or to governmental entities that control or process personal data | Rules that do govern government processing |
| EU Directive 2018/1972 | Art. 110(1)-(2) | Member States ensure public warnings are transmitted by mobile number-based interpersonal communications providers; alternatives must be equivalent in coverage and capacity | n/a (global comparison only) |

### Read on 2026-11-08 from the downloaded files (telecom law, rumours law, TDRA licence, Decree-Law 8/2025)

| Source | Article | What it says (paraphrase) | What it does NOT establish |
|---|---|---|---|
| Decree-Law 8/2025 (EN official translation) | Art. 4(2), 4(5) | Civil defence authority studies hazards and prepares plans "in coordination with" NCEMA, and establishes "a public warning system for the population", in coordination with NCEMA | "Establish" is not "operate", "trigger" or "cancel"; who authors an individual alert |
| Decree-Law 8/2025 | Art. 8(1) | Coordination between the civil defence authority, the Armed Forces and NCEMA on cooperation foundations | Alerting procedures |
| Telecom Decree-Law 3/2003 (EN official translation) | Art. 3(3), 10(3) | The High Committee / TDRA Board may issue general directives on the telecom sector "in the interest of national security or international relations" (the Board's, with Cabinet approval) | Any emergency-warning or cell-broadcast duty. A full-text search for emergenc*, warning, alert, disaster, crisis found none |
| TDRA Licence 3/2026 | Art. 12.6 | Licensee maintains technical capability to operate and restore its network "under emergency and contingency conditions" | A duty to deliver public alerts |
| TDRA Licence 3/2026 | Art. 16.7 | The Arabic version is binding; the official English is for guidance. So English citations are `official_translation_arabic_prevails` | n/a |
| TS FS 001 v2.0 | Version-control table | v2.0 (25 Nov 2019) was "updated [with] National Emergency Crisis and Disaster Management Authority comments" | That NCEMA owns or operates UAE-Alert: review comments are not ownership |
| Rumours and cybercrime law 34/2021 (EN official translation) | Art. 52(1)-(2) | Criminalises spreading false news or reports "contrary to what has been announced officially", with a heavier penalty during emergencies | Anything about errors in official alerts or how an official correction is made. It is not a basis for any institution mandate |

### NCEMA Decree-Law 2/2011 (Arabic PDF, sha256 `3078bca6...735c`, read in full 2026-11-08)

Paraphrases are ours, written from the Arabic; they are not a translation of the law.

| Article | What it says (paraphrase) | What it does NOT establish |
|---|---|---|
| Art. 2 | Creates the Authority as a public body with legal personality, reporting to the (Supreme National Security) Council | Anything about alerting |
| Art. 5 (items 1-12) | Competences, expressly "without prejudice to the competences that laws give other relevant bodies": take part in preparing and coordinating response plans; supervise response-capability development; take part in the national risk register; manage emergencies "through coordination and cooperation with the relevant bodies" (5(4)); coordinate the roles of relevant bodies when an emergency occurs (5(5)); take part in exercises; propose legislation | **No item gives NCEMA power to issue, authorise, trigger or cancel public alerts.** Its role is coordination |
| Art. 7(7) | The Board approves the national response plan and the mechanism for dealing between the Authority and other bodies | The content of that plan (not in the corpus) |
| Art. 12(3)-(4) | Preparedness/response plans are the unified national mechanism; the Executive Regulation sets the classification of events and the roles of each body | Roles themselves: they sit in the Executive Regulation, which is **not in the KB** |
| Art. 13 "second" (5) | Relevant bodies, each within its competence, "prepare and organise public and private warning means" | Which body triggers or cancels a particular alert |
| Art. 14(2) | Relevant bodies, each within its competence and in coordination with NCEMA, take measures including "warning community members and guiding them"; roles set by the Executive Regulation | Who has final say on content or timing |
| Art. 15(2) | The National Security Adviser may direct the determination of the emergency level and activation of emergency teams | That this covers public alerts |
| Art. 24 | NCEMA coordinates with all media to unify the media message during emergencies | Control of mobile alerts |
| Art. 25 | NCEMA makes arrangements to provide information on developments and protection means, including for non-Arabic speakers and persons with special needs | A correction or cancellation procedure |
| Art. 23(3)-(5) | Information-sharing duties; refusals are escalated to NCEMA | n/a |
| Art. 26 | Bodies provide liaison elements to the operations centre | Alert procedures |
| Art. 31(3) | The National Security Adviser or delegate may temporarily use communications networks and satellites, with fair compensation | Peacetime alert operation |
| Art. 42 | The Board issues the Executive Regulation | Its content or date (not in the KB) |

**Consequence for the agent profiles (R2):** from this law NCEMA may be described as *coordinating* and *informing*, never as the
body that issues, authorises or cancels alerts. Many operative details are delegated to an Executive Regulation that the
public corpus does not contain: that is a `PUBLIC_DOCUMENTATION_LIMITATION`, not a policy gap, unless a later search of
official sources shows the regulation is published and still has no relevant provision.

Not yet checked: whether later amendments changed these articles (the platform copy is dated 2026; no amendment list was
retrieved).
