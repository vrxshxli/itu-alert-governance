"""Chunker tests on the real downloaded sources (skipped when kb/raw has not been populated)."""
from pathlib import Path

import pytest

from kb import chunker

RAW = Path(__file__).resolve().parents[1] / "kb" / "raw"
pytestmark = pytest.mark.skipif(not (RAW / "ae-dl-8-2025-faacd.pdf").exists(), reason="run scripts/fetch_sources.sh first")


@pytest.fixture(scope="module")
def recs():
    return {r["id"]: r for r in chunker.build_all("test")}


def test_every_record_has_citation_metadata(recs):
    need = {"chunk_id", "doc_id", "title", "jurisdiction", "institution", "article", "date", "language", "url", "kb_version"}
    for r in recs.values():
        assert need <= set(r["metadata"]), r["id"]
        assert r["metadata"]["url"].startswith("http") and r["metadata"]["article"]
        assert r["id"] == r["metadata"]["chunk_id"]


def test_ids_unique():
    ids = [r["id"] for r in chunker.build_all("test")]
    assert len(ids) == len(set(ids))


def test_long_article_split_at_clauses_keeps_4_5_whole(recs):
    parts = [r for i, r in recs.items() if i.startswith("ae-dl-8-2025-faacd:art4:")]
    assert len(parts) >= 2
    assert all(p["text"].startswith("Article (4)") for p in parts)
    holder = [p for p in parts if "public warning system" in p["text"]]
    assert len(holder) == 1 and "National Emergency, Crisis and Disasters" in holder[0]["text"].split("public warning system")[1]


def test_licence_keeps_english_only_and_art8(recs):
    t = recs["ae-tdra-licence-3-2026:art8"]["text"]
    assert "public emergency has arisen" in " ".join(t.split())  # the PDF breaks lines mid-phrase
    assert not chunker.ARABIC_RE.search(t)


def test_eu_art110_present_and_global(recs):
    r = recs["eu-eecc-2018-1972:art110"]
    assert "public warnings are transmitted by providers of mobile number-based" in r["text"]
    assert r["metadata"]["authority_status"] == "reference_global"


def test_repealed_law_labelled(recs):
    cda = [r for r in recs.values() if r["metadata"]["doc_id"] == "ae-dl-35-2024-cda"]
    assert cda and all(r["metadata"]["authority_status"] == "historical_repealed" for r in cda)


def test_arabic_article_split_finds_all_44():
    ar = chunker.arabic_articles("test")
    assert sorted(map(int, ar)) == list(range(1, 45))


def test_translation_chunks_are_labelled_unofficial_and_capped():
    recs = chunker.build_all("test", {"5": "Competences. 1. ..."})
    t = [r for r in recs if r["id"].startswith("ae-dl-2-2011-ncema-en-unofficial")][0]
    assert t["text"].startswith("[UNOFFICIAL TRANSLATION, NON-AUTHORITATIVE]")
    m = t["metadata"]
    assert m["translation_status"] == "unofficial_translation" and m["max_evidence_status"] == "partially_supported"
    assert m["arabic_text"].startswith("املادة") and "uaelegislation.gov.ae/ar/" in m["arabic_url"]
