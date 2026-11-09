import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kb.authority import (  # noqa: E402
    can_support_current_mandate, cap_evidence, format_citation, is_coordination_only, registry, where_filter,
)


def test_registry_loads_and_translation_is_registered():
    r = registry()
    assert "ae-dl-2-2011-ncema" in r and "ae-dl-2-2011-ncema-en-unofficial" in r
    assert r["ae-dl-2-2011-ncema-en-unofficial"]["translation_status"] == "unofficial_translation"


def test_translation_only_claim_is_capped_at_partially_supported():
    assert cap_evidence("confirmed", ["ae-dl-2-2011-ncema-en-unofficial"], current_mandate_claim=True) == "partially_supported"
    # the Arabic original can support confirmed
    assert cap_evidence("confirmed", ["ae-dl-2-2011-ncema"], current_mandate_claim=True) == "confirmed"


def test_repealed_law_never_supports_current_authority():
    assert not can_support_current_mandate("ae-dl-35-2024-cda")
    assert cap_evidence("confirmed", ["ae-dl-35-2024-cda"], current_mandate_claim=True) == "not_established_from_public_sources"
    assert "historical_repealed" not in where_filter("current")["authority_status"]["$in"]
    assert "historical_repealed" in where_filter("history")["authority_status"]["$in"]


def test_global_and_technical_sources_cannot_ground_uae_mandates():
    for d in ["us-fcc-hawaii-2018", "eu-eecc-2018-1972", "ae-tdra-ts-fs-001", "itu-x1303bis-cap", "ae-ai-strategy-2031"]:
        assert not can_support_current_mandate(d), d


def test_citations_show_arabic_original_and_labels():
    c = format_citation("ae-dl-2-2011-ncema-en-unofficial", "Article (5)", arabic_article="المادة (5)")
    assert "https://uaelegislation.gov.ae/ar/legislations/4461/download" in c
    assert "unofficial translation, non-authoritative" in c and "المادة (5)" in c
    assert "Arabic text prevails" in format_citation("ae-dl-8-2025-faacd", "Art. (4)(5)")
    assert "REPEALED" in format_citation("ae-dl-35-2024-cda", "Art. (3)(8)")


def test_coordination_clause_is_not_a_mandate_for_ncema():
    art_4_5 = ("Establish a public warning system for the population against potential hazards, in coordination with "
               "the National Emergency, Crisis and Disasters Management Authority.")
    assert is_coordination_only(art_4_5, "National Emergency, Crisis and Disasters Management Authority",
                                power_holder_named_as_subject=False)


def test_every_registered_authority_status_is_reachable_by_some_mode():
    """Regression: 'framework' documents were unreachable in every retrieval mode."""
    from kb.authority import registry, where_filter

    reachable = set()
    for mode in ("current", "global", "history", "framework"):
        w = where_filter(mode)["authority_status"]
        reachable |= set(w["$in"]) if isinstance(w, dict) else {w}
    assert {s["authority_status"] for s in registry().values()} <= reachable
