"""Unit tests for verification.external_match: OpenAlex + Crossref clients."""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

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

CROSSREF_FIXTURE = {
    "message": {
        "items": [
            {
                "DOI": "10.5678/another",
                "title": ["A second NUMT study"],
                "abstract": "<jats:p>NUMTs interfere with variant calling.</jats:p>",
                "issued": {"date-parts": [[2023]]},
                "author": [{"given": "Alice", "family": "Smith"}],
                "URL": "https://doi.org/10.5678/another",
            }
        ]
    }
}


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


@pytest.mark.unit
def test_search_crossref_returns_parsed_matches():
    from research_assistant.verification.external_match import search_crossref

    fake = type("R", (), {"json": lambda self: CROSSREF_FIXTURE, "raise_for_status": lambda self: None})()
    with patch("research_assistant.verification.external_match.httpx.get", return_value=fake):
        results = search_crossref("NUMT interfere variant calling", limit=5)

    assert len(results) == 1
    m = results[0]
    assert m["title"] == "A second NUMT study"
    assert m["year"] == 2023
    assert m["doi"] == "10.5678/another"
    assert m["authors"] == "Smith, Alice"
    assert "NUMTs interfere with variant calling." in m["abstract"]   # JATS stripped
    assert m["url"] == "https://doi.org/10.5678/another"


@pytest.mark.unit
def test_cached_search_hits_cache_on_second_call(tmp_path, monkeypatch):
    """Two identical search calls should make exactly one HTTP request."""
    from research_assistant.verification import external_match as em

    monkeypatch.setattr(em, "CACHE_PATH", tmp_path / "test_cache.shelf")

    call_count = {"n": 0}

    def fake_get(url, params=None, timeout=None):
        call_count["n"] += 1
        return type("R", (), {"json": lambda self: OPENALEX_FIXTURE, "raise_for_status": lambda self: None})()

    monkeypatch.setattr(em.httpx, "get", fake_get)

    r1 = em.cached_search("openalex", "NUMT contamination", limit=5)
    r2 = em.cached_search("openalex", "NUMT contamination", limit=5)

    assert call_count["n"] == 1, "Second call should hit cache, not HTTP"
    assert r1 == r2


@pytest.mark.unit
def test_cache_expires_after_ttl(tmp_path, monkeypatch):
    from research_assistant.verification import external_match as em

    monkeypatch.setattr(em, "CACHE_PATH", tmp_path / "test_cache.shelf")
    monkeypatch.setattr(em, "CACHE_TTL_SECONDS", 0)  # immediate expiry

    call_count = {"n": 0}

    def fake_get(*a, **kw):
        call_count["n"] += 1
        return type("R", (), {"json": lambda self: OPENALEX_FIXTURE, "raise_for_status": lambda self: None})()

    monkeypatch.setattr(em.httpx, "get", fake_get)

    em.cached_search("openalex", "NUMT", limit=5)
    em.cached_search("openalex", "NUMT", limit=5)
    assert call_count["n"] == 2, "Expired cache should force a refetch"
