"""Unit tests for verification.external_match: OpenAlex + Crossref clients."""
from __future__ import annotations

import pytest


@pytest.mark.unit
def test_cache_key_is_stable_and_source_aware():
    from research_assistant.verification.external_match import _cache_key

    k1 = _cache_key("openalex", "NUMT filtering")
    k2 = _cache_key("openalex", "NUMT filtering")
    k3 = _cache_key("crossref", "NUMT filtering")
    k4 = _cache_key("openalex", "Different query")

    assert k1 == k2, "Same source+query must produce the same key"
    assert k1 != k3, "Different source must produce a different key"
    assert k1 != k4, "Different query must produce a different key"
    assert isinstance(k1, str) and len(k1) == 64, "Cache key should be hex sha256"


from unittest.mock import patch

OPENALEX_FIXTURE = {
    "results": [
        {
            "id": "https://openalex.org/W123",
            "title": "NUMT contamination in clinical mtDNA sequencing",
            "abstract_inverted_index": {"NUMT": [0], "contamination": [1], "is": [2], "common": [3]},
            "publication_year": 2024,
            "doi": "https://doi.org/10.1234/example",
            "authorships": [{"author": {"display_name": "Doe, Jane"}}],
        }
    ]
}


@pytest.mark.unit
def test_search_openalex_returns_parsed_matches():
    from research_assistant.verification.external_match import search_openalex

    fake_response = type("R", (), {"json": lambda self: OPENALEX_FIXTURE, "raise_for_status": lambda self: None})()
    with patch("research_assistant.verification.external_match.httpx.get", return_value=fake_response):
        results = search_openalex("NUMT contamination in clinical mtDNA", limit=5)

    assert len(results) == 1
    m = results[0]
    assert m["title"].startswith("NUMT contamination")
    assert m["year"] == 2024
    assert m["doi"] == "10.1234/example"             # bare DOI, no URL prefix
    assert m["authors"] == "Doe, Jane"
    assert "NUMT contamination is common" in m["abstract"]
    assert m["url"] == "https://openalex.org/W123"
