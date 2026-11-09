# Knowledge-base sources (Step 0: availability check)

Checked: **2026-11-08**. Only official publications (legislation portals, regulators, standards bodies, official
investigation reports). News articles are not KB sources.

**How hashes were taken.** `sha256` is over the original file bytes as served on the access date, computed in the
browser (`crypto.subtle.digest`) from the official URL. `scripts/fetch_sources.sh` re-downloads each file into
`kb/raw/` and checks the hash; a mismatch means the publisher changed the file, which must be reviewed before re-ingesting.

**Redistribution.** Where the publisher reserves all rights, the public repo contains only the URL, metadata, hash and
our extraction scripts, not the text (column *Text in public repo*). See section 4.

**Authority status** (current / repealed / unofficial translation / technical / global) and the evidence ceiling of each
source are in the machine-readable registry `kb/sources.yaml`; the rules that use them are in `kb/AUTHORITY_RULES.md`.
Decisions of 2026-11-08: the Arabic NCEMA law is ingested as authoritative, and any English rendering is stored only as
`unofficial_translation`; the repealed 2024 law is historical context only; TDRA Licence 3/2026 is the current source for
operator obligations.

## 1. UAE: legal and regulatory sources

| doc_id | Document | Issuer | Status (per portal) | Language / translation | URL | Bytes | sha256 | Text in public repo |
|---|---|---|---|---|---|---|---|---|
| `ae-dl-2-2011-ncema` | Federal Decree-Law No. (2) of 2011 on the Establishment of the National Emergency, Crisis and Disasters Management Authority (NCEMA) | UAE Legislation Platform (Ministry of Cabinet Affairs) | listed "as amended" in later laws; portal page in Arabic only | **Arabic only. No English text on the official platform** (`/en/legislations/4461` returns "Page not found") | https://uaelegislation.gov.ae/ar/legislations/4461/download | 309,410 | `3078bca67808d107c8470121b9a280b088ea00621183dcb69fb8d022b2f6735c` | No |
| `ae-dl-8-2025-faacd` | Federal Decree by Law No. (8) of 2025 Regarding the Establishment of the Federal Authority for Ambulance and Civil Defense | same | Active; issued 08 Sep 2025, in force 01 Jan 2026 | English, official platform translation (Arabic prevails) | https://uaelegislation.gov.ae/en/legislations/3231/download | 122,360 | `f552b3dee96488e5838aead243920ae72303585ec5ef054ffacbe0c9d5d22e4b` | No |
| `ae-dl-35-2024-cda` | Federal Decree-Law No. (35) of 2024 on the Reorganization of the Civil Defence Authority | same | **Repealed** by Decree-Law 8/2025 Art. (19); portal page removed, PDF still served | English, official platform translation | https://uaelegislation.gov.ae/en/legislations/2771/download | 100,020 | `73a75bfec06bcf60995a9572f405e03e3e8ee021d7f9f01e0efe62b27c75dc21` | No |
| `ae-dl-3-2003-telecom` | Federal Decree-Law No. (3) of 2003 Regulating Telecommunications | same | Active; 3 amendments; portal "last update" 27 Sep 2020 | English, official platform translation | https://uaelegislation.gov.ae/en/legislations/1132/download | 227,969 | `ad162193811d06fc224cc9997abd7bafc3ebcc20a53df1e45708b34172aa1bab` | No |
| `ae-tdra-uae-alert-table` | TDRA UAE public-warning (Cell Broadcast) handset channel and behaviour table (alert classes, channel IDs, mute-mode behaviour, primary/secondary language channels) | Telecommunications and Digital Government Regulatory Authority | Server `Last-Modified` 06 Dec 2021; newer versions may exist (not found on 2026-11-08) | Bilingual Arabic/English table | https://tdra.gov.ae/userfiles/assets/lgz6mOeOihm.pdf | 68,828 | `4e2fdc285cb5d34818c0208862584cf30854e968a8fbf3d404f8613bf25f3eec` | No |
| `ae-tdra-licence-3-2026` | TDRA Public Telecommunication Licence No. (3) of 2026 (Emirates Integrated Telecommunications Company PJSC), public version: **current operator obligations**, Art. 8 (public emergencies; public interest, safety and national security; assumption of control), Art. 12.4 (resilience) | TDRA | Signed 06 Aug 2026; effective 09 Aug 2026 to 08 Aug 2046 | Bilingual English/Arabic; language clause Art. 16.7 not yet read | https://tdra.gov.ae/-/media/About/LICENSING/EN/Licence-32026-EITC-Public.ashx | 752,881 | `ccafd4ed2d5a960bc1fb2ff27c6161a95a948ee2547ac13b87589a79ddcf7924` | No |
| `ae-tdra-ts-fs-001` | TDRA Technical Specification TS FS 001 v2.0, Enabling Cell Broadcast for National Public Warning Service (UAE-Alert) | TDRA | Document date 25 Nov 2019; handsets from 31 Dec 2019; server `Last-Modified` 19 Sep 2022 | English (class titles bilingual) | https://tdra.gov.ae/-/media/About/Type-Approval/Technical-Standards-2021/TS-FS-001-Emergency-Broadcast.ashx | 727,769 | `a5776742439647dcd8f48e12ab968c501162c686b67b331ce1a9473f22e3c737` | No |
| `ae-dl-45-2021-pdpl` | Federal Decree by Law No. (45) of 2021 Concerning the Protection of Personal Data | UAE Legislation Platform | Active; in force 02 Jan 2022 | English, official platform translation | https://uaelegislation.gov.ae/en/legislations/1972/download | 194,597 | `d5d5f9e93bd6c0dc2afe79776f3101bcd599e4400a67309bc0b378b2812bcf3a` | No |
| `ae-dl-34-2021-rumours` | Federal Decree-Law No. (34) of 2021 on Countering Rumors and Cybercrimes | same | Active; 1 amendment; portal "last update" 04 Apr 2024 | English, official platform translation | https://uaelegislation.gov.ae/en/legislations/1526/download | 222,615 | `f438fdf264b93c9d108ff4d40633aa55e798e63f47a951943a372ea73ee938e1` | No |
| `ae-ai-strategy-2031` | UAE National Strategy for Artificial Intelligence 2031 | UAE Government portal (u.ae) | Published strategy | English (Arabic edition also published) | https://u.ae/-/media/AI-publications/UAE-National-Strategy-for-Artificial-Intelligence-2031.pdf | pending | **pending**: text retrieved via web fetch on 2026-11-08, but the URL returned HTTP 404 to the browser the same day, so no byte hash yet | No |

Optional UAE additions (verified to exist, not yet selected): Federal Decree No. (44) of 2021 Establishing the Emirates
Data Office (`/en/legislations/2433`, sha256 `06ed03b7...28cd`), Federal Decree by Law No. (11) of 2025 Establishing the
National Media Authority (`/en/legislations/3943`), Cabinet Resolution No. (19) of 2020 on Government Work Under
Emergency Circumstances (`/en/legislations/1410`).

## 2. Global comparison sources

| doc_id | Document | Issuer | Language | URL | Bytes | sha256 | Text in public repo |
|---|---|---|---|---|---|---|---|
| `us-fcc-hawaii-2018` | Report and Recommendations: Hawaii Emergency Management Agency January 13, 2018 False Alert (April 2018) | FCC Public Safety and Homeland Security Bureau | English | https://docs.fcc.gov/public/attachments/DOC-350119A1.pdf (official text version: `.../DOC-350119A1.txt`, sha256 `c1d4f96806c98226f8ebadfe56ddb4487edb7a2d2b0ec22f9f6b7d4e0d93e509`) | 788,570 | `d19c432a20ac86e14165221aa906d780c97c87489afabc23a6b61a04d48235c0` | Yes (US federal government work) |
| `eu-eecc-2018-1972` | Directive (EU) 2018/1972, European Electronic Communications Code: Art. 110 (Public warning system), Art. 111, Recital (294) | EUR-Lex (Publications Office of the EU) | English (authentic EU language version) | https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32018L1972 | 1,558,192 (HTML) | `d4716af89fac536fc2a8e6732c6a95ffc117c69e800ea5221325b199ea70bc71` | Yes, extracted articles only (EU reuse policy, source acknowledged) |
| `itu-x1303bis-cap` | Recommendation ITU-T X.1303 bis (03/2014): Common alerting protocol (CAP 1.2) | ITU-T | English | https://www.itu.int/en/ITU-D/Emergency-Telecommunications/Documents/2020/T-REC-X.1303bis-201403-.pdf | 1,091,696 | `79ec13413942e8e36526ddd38b4ce6d9a9f3197f106d07277e239b255fd45114` | No (ITU copyright) |
| `itu-ew4all-arab-cb-2026` | ITU Partner Brief: Cell Broadcast for Early Warnings in the Arab States (Oct 2026) | ITU (EW4All) | English | https://www.itu.int/en/ITU-D/Emergency-Telecommunications/Documents/2026/EW4All/Arab%20States_CB_Partner%20Brief_Oct%202026.pdf | 106,917 | `01906532c98571bec2c75b6a76ff365655cc05f46da54ca9600e755d0162dc51` | No (ITU copyright) |

Japan J-Alert: not added (no official source verified yet; optional per brief 14.9).

## 3. Framework sources (for the report's alignment sections, not for agent mandates)

| doc_id | Document | URL | Bytes | sha256 |
|---|---|---|---|---|
| `itu-y3172-2019` | Recommendation ITU-T Y.3172 (06/2019): Architectural framework for machine learning in future networks including IMT-2020 | https://www.itu.int/rec/dologin_pub.asp?lang=e&id=T-REC-Y.3172-201906-I!!PDF-E&type=items | 1,145,173 | `e42f9a3be3f951d3e19b9007f876f0b389c81b4693f0d8576e18185a1acfe67b` |
| `itu-ai-ready-2-0` | AI Ready: Analysis Towards a Standardized Readiness Framework, Report 2.0 (title as listed on the ITU publications page; cover and edition date not yet checked against the PDF) | https://www.itu.int/dms_pub/itu-t/opb/ai4g/T-AI4G-AI4GOOD-2025-6-PDF-E.pdf | 1,109,667 | `71191768d46b60778c15f8d62b162aff73a319785cfc31ebf76bb944b0c68273` |

Byte sizes match the copies in the ITU reference repo (`T-REC-Y.3172-201906-I!!PDF-E.pdf`, `AI_Ready_Framework_2025.pdf`).

## 4. Licensing and redistribution notes

- **UAE Legislation Platform**: pages carry "Copyright © 2026 Ministry of Cabinet Affairs. All rights reserved." Every English
  page also says the English is a translation, and that "In case of conflict, the Arabic text will prevail". Treatment:
  the public repo holds URL, metadata and hash only; agents cite the English article but the citation record keeps
  `translation_status = official_translation_arabic_prevails`.
- **TDRA, u.ae, ITU**: no open licence found, so URL and hash only.
- **FCC**: US federal government work, not subject to copyright in the US; text may be included.
- **EUR-Lex**: EU reuse policy permits reuse with source acknowledgement; we include only the extracted articles we cite.
- The KB export (`kb/export/*.jsonl`) contains chunk text. It is for the ITU AI for Good Lab environment, not for the
  public repo, unless the organisers confirm otherwise.

## 5. Context only (not a KB source)

The scenario is fictional. It is inspired only by the class of public-alert failure described in NCEMA's public notice of
26 June 2026 (a technical malfunction in the early-warning system resulted in incorrect warning messages). The WAM article
(https://www.wam.ae/en/article/c0x4feq-ncema-announces-handling-unintended-malfunction) did not render in our browser on
2026-11-08, so we do not quote it. We describe the real event no further than that.
