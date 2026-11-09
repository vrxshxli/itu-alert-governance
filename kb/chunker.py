"""Article-aware chunking of the source documents into KB records.

Output record: {"id", "text", "metadata"}; metadata carries doc_id, title, jurisdiction, institution, article, date,
language, translation_status, authority_status, url, kb_version, chunk_id (the id).

Strategies
  articles      laws and licences: one chunk per "Article (N)" (split into parts when long)
  arabic        NCEMA Arabic original: one record per article, stored UNEMBEDDED-in-practice (the embedding model is
                English-only); each translation chunk carries its Arabic article text in `arabic_text`
  pages         standards, reports, briefs: ~256-word windows with 30-word overlap, labelled with page numbers
  eu_articles   only the EU articles we verified (Art. 110, 111, Recital 294)

Extraction caveat (recorded, not hidden): the NCEMA PDF's Arabic text layer reorders letters around the definite
article ("ال"), so the stored Arabic is a lossy machine extraction. The PDF at the registered URL and hash is the
authority; citations always name the article number.
"""
from __future__ import annotations

import html as _html
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "kb" / "raw"
BIDI = "‪‫‬‭‮‎‏⁦⁧⁨⁩"
ARABIC_RE = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
WINDOW, OVERLAP, MAX_ARTICLE_WORDS = 256, 30, 330

# Dates only where the source itself states them (file name, URL, or text).
DOC_DATES = {
    "ae-dl-2-2011-ncema": "2011-06-19", "ae-dl-8-2025-faacd": "2025-09-08", "ae-dl-35-2024-cda": "2024",
    "ae-dl-3-2003-telecom": "2003", "ae-tdra-licence-3-2026": "2026", "ae-tdra-ts-fs-001": "2019-11-25",
    "ae-tdra-uae-alert-table": "", "ae-dl-45-2021-pdpl": "2021", "ae-dl-34-2021-rumours": "2021",
    "us-fcc-hawaii-2018": "2018", "eu-eecc-2018-1972": "2018-12-11", "itu-x1303bis-cap": "2014-03",
    "itu-ew4all-arab-cb-2026": "2026-10", "itu-y3172-2019": "2019-06", "itu-ai-ready-2-0": "2025",
}
STRATEGY = {
    "ae-dl-8-2025-faacd": "articles", "ae-dl-35-2024-cda": "articles", "ae-dl-3-2003-telecom": "articles",
    "ae-dl-45-2021-pdpl": "articles", "ae-dl-34-2021-rumours": "articles", "ae-tdra-licence-3-2026": "articles",
    "ae-tdra-ts-fs-001": "pages", "ae-tdra-uae-alert-table": "pages", "us-fcc-hawaii-2018": "pages",
    "itu-x1303bis-cap": "pages", "itu-ew4all-arab-cb-2026": "pages", "itu-y3172-2019": "pages",
    "itu-ai-ready-2-0": "pages", "eu-eecc-2018-1972": "eu_articles",
}


def _registry() -> dict:
    return {s["doc_id"]: s for s in yaml.safe_load((ROOT / "kb" / "sources.yaml").read_text(encoding="utf-8"))["sources"]}


def _meta(src: dict, kb_version: str, **kw) -> dict:
    m = {"doc_id": src["doc_id"], "title": src["title"], "jurisdiction": src.get("jurisdiction", ""),
         "institution": src.get("institution", ""), "date": DOC_DATES.get(src["doc_id"], ""),
         "language": src.get("language", "en"), "translation_status": src.get("translation_status", "original"),
         "authority_status": src["authority_status"], "url": src["url"], "kb_version": kb_version}
    m.update(kw)
    return m


def _pages(pdf: Path) -> list[str]:
    import pymupdf

    out = []
    for p in pymupdf.open(pdf):
        t = p.get_text()
        for c in BIDI:
            t = t.replace(c, "")
        out.append(t)
    return out


def _words_windows(words: list[str]) -> list[tuple[int, int]]:
    spans, i = [], 0
    while i < len(words):
        spans.append((i, min(i + WINDOW, len(words))))
        if i + WINDOW >= len(words):
            break
        i += WINDOW - OVERLAP
    return spans


def english_only(text: str) -> str:
    """Bilingual licence text: keep lines without Arabic script for embedding/citation of the English version."""
    return "\n".join(l for l in text.splitlines() if not ARABIC_RE.search(l))


def _clean(t: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", t)).strip()


def _split_by_clauses(text: str, budget: int = 250) -> list[str] | None:
    """Split a long article at numbered-clause boundaries ("1. ", "2. " ...), never mid-clause. Every part repeats the
    article heading so it stays citable on its own. Returns None if a single clause is too long (caller falls back)."""
    lines = text.split("\n")
    head_lines = []
    for ln in lines[:3]:
        if re.match(r"\s*\d+[.)]\s", ln):
            break
        head_lines.append(ln)
    header = " ".join(head_lines).strip()
    body = "\n".join(lines[len(head_lines):])
    clauses = [c.strip() for c in re.split(r"(?m)^(?=\s*\d+[.)]\s)", body) if c.strip()]
    if len(clauses) < 2 or any(len(c.split()) > MAX_ARTICLE_WORDS for c in clauses):
        return None
    parts, cur, n = [], [], 0
    for c in clauses:
        w = len(c.split())
        if cur and n + w > budget:
            parts.append(cur)
            cur, n = [], 0
        cur.append(c)
        n += w
    parts.append(cur)
    return [(header + "\n" if header else "") + "\n".join(p) for p in parts]


# ---------- strategies ----------
def chunk_articles(src: dict, kb_version: str) -> list[dict]:
    pages = _pages(RAW / f"{src['doc_id']}.pdf")
    full = "\n".join(pages)
    if src["doc_id"] == "ae-tdra-licence-3-2026":
        full = english_only(full)
    head = re.compile(r"^\s*Article\s*\(?\s*(\d+)\s*\)?\s*(?=\S|$)", re.M)
    marks = [(m.start(), m.group(1)) for m in head.finditer(full)]
    bodies: dict[str, tuple[int, str]] = {}
    for k, (pos, num) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(full)
        body = full[pos:end]
        # table-of-contents / cross-reference hits are short: keep the longest body per article number
        if num not in bodies or len(body) > len(bodies[num][1]):
            bodies[num] = (pos, body)
    out = []
    for num, (_, body) in sorted(bodies.items(), key=lambda kv: kv[1][0]):
        text = _clean(body)
        if len(text.split()) < 12:
            continue
        words = text.split()
        if len(words) <= MAX_ARTICLE_WORDS:
            parts = [text]
        else:
            parts = _split_by_clauses(text) or [" ".join(words[a:b]) for a, b in _words_windows(words)]
        for k, part in enumerate(parts, 1):
            cid = f"{src['doc_id']}:art{num}" + (f":p{k}" if len(parts) > 1 else "")
            out.append({"id": cid, "text": part, "metadata": _meta(
                src, kb_version, chunk_id=cid, article=f"Art. {num}" + (f" (part {k}/{len(parts)})" if len(parts) > 1 else ""))})
    return out


def chunk_pages(src: dict, kb_version: str) -> list[dict]:
    path = RAW / f"{src['doc_id']}.pdf"
    pages = _pages(path)
    words, owner = [], []
    for pno, t in enumerate(pages, 1):
        for w in t.split():
            words.append(w)
            owner.append(pno)
    out = []
    for k, (a, b) in enumerate(_words_windows(words), 1):
        p0, p1 = owner[a], owner[b - 1]
        label = f"p. {p0}" if p0 == p1 else f"pp. {p0}-{p1}"
        cid = f"{src['doc_id']}:w{k:03d}"
        out.append({"id": cid, "text": " ".join(words[a:b]), "metadata": _meta(src, kb_version, chunk_id=cid, article=label)})
    return out


def chunk_eu(src: dict, kb_version: str) -> list[dict]:
    t = (RAW / "eu-eecc-2018-1972.html").read_text(encoding="utf-8", errors="replace")
    s = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
    s = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s)))
    out = []
    for art, nxt in (("110", "Article 111"), ("111", "Article 112")):
        i = s.find(f"Article {art} ")
        j = s.find(nxt, i)
        # first hit can be a cross-reference; the heading is followed by its title and "1."
        heads = [m.start() for m in re.finditer(rf"Article {art} [A-Z]", s)]
        i = heads[0] if heads else i
        j = s.find(nxt, i)
        cid = f"eu-eecc-2018-1972:art{art}"
        out.append({"id": cid, "text": s[i:j].strip(), "metadata": _meta(src, kb_version, chunk_id=cid, article=f"Art. {art}")})
    k = s.find("(294)")
    if k >= 0:
        cid = "eu-eecc-2018-1972:rec294"
        out.append({"id": cid, "text": s[k:k + 1400].split("(295)")[0].strip(),
                    "metadata": _meta(src, kb_version, chunk_id=cid, article="Recital (294)")})
    return out


ART_AR = re.compile(r"املادة\s*\(\s*(\d+)\s*\)|املا\(\s*دة\s*(42)\s*\)")


def arabic_articles(kb_version: str) -> dict[str, str]:
    """{article number: lossy Arabic extraction} from the official Arabic PDF."""
    full = "\n".join(_pages(RAW / "ae-dl-2-2011-ncema.pdf"))
    full = re.sub(r"[ \t]*\n[ \t]*", " ", full)
    marks = [(m.start(), m.group(1) or m.group(2)) for m in ART_AR.finditer(full)]
    res: dict[str, str] = {}
    for k, (pos, num) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(full)
        res[num] = re.sub(r"\s+", " ", full[pos:end]).strip()
    return res


def strip_trailing_heading(text: str) -> str:
    """The PDF puts the NEXT section's title at the end of an article ("Declaration of the stricken area"). Drop a final
    short line that is not a sentence (<= 8 words, no closing . ; : and not a numbered item)."""
    lines = text.rstrip().split("\n")
    while len(lines) > 1:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        if (len(last.split()) <= 8 and not re.search(r"[.;:]$", last) and not re.match(r"\d+[.)]|[a-z]\.", last)
                and not re.match(r"(Date|Corresponding)\b", last)):
            lines.pop()
            continue
        break
    return "\n".join(lines).rstrip()


def build_all(kb_version: str, translations: dict | None = None) -> list[dict]:
    """All records. `translations` = {article number: English text} for the NCEMA unofficial translation."""
    reg = _registry()
    recs: list[dict] = []
    for doc_id, strat in STRATEGY.items():
        src = reg[doc_id]
        recs += {"articles": chunk_articles, "pages": chunk_pages, "eu_articles": chunk_eu}[strat](src, kb_version)
    # NCEMA: Arabic original is authoritative; the retrievable text is the labelled unofficial English translation
    ncema = reg["ae-dl-2-2011-ncema"]
    ar = arabic_articles(kb_version)
    if translations:
        for num, en in sorted(translations.items(), key=lambda kv: int(kv[0])):
            en = strip_trailing_heading(en)
            cid = f"ae-dl-2-2011-ncema-en-unofficial:art{num}"
            meta = _meta(ncema, kb_version, chunk_id=cid, article=f"Art. {num}", translation_status="unofficial_translation",
                         language="en", arabic_text=ar.get(num, ""), arabic_url=ncema["url"], max_evidence_status="partially_supported")
            meta["doc_id"] = "ae-dl-2-2011-ncema-en-unofficial"
            meta["title"] = ncema["title"] + " (UNOFFICIAL English translation, non-authoritative)"
            recs.append({"id": cid, "text": "[UNOFFICIAL TRANSLATION, NON-AUTHORITATIVE] " + en, "metadata": meta})
    return recs
