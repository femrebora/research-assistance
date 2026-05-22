"""Tests for claim_verify.py — claim extraction and label parsing."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from claim_verify import _parse_label_block, extract_claims


class TestExtractClaims:
    def test_picks_cited_sentences(self):
        text = (
            "NUMT contamination is a clinical concern [@smith2024]. "
            "The weather is fine today. "
            "Heteroplasmy levels increased significantly under stress [@jones2023]."
        )
        claims = extract_claims(text)
        assert any("NUMT contamination" in c for c in claims)
        assert any("Heteroplasmy" in c for c in claims)
        assert not any("weather" in c for c in claims)

    def test_factual_signal_without_citation(self):
        text = (
            "Recent work demonstrates that mitochondrial heteroplasmy varies by tissue. "
            "We had coffee. "
            "This study shows a clear association with disease severity."
        )
        claims = extract_claims(text)
        assert any("demonstrates" in c for c in claims)
        assert any("shows a clear association" in c for c in claims)
        assert not any("coffee" in c for c in claims)

    def test_respects_min_chars(self):
        text = "Short. Tiny sentence here is too small. This is a much longer factual statement that clearly shows a real association with the outcome of interest."
        claims = extract_claims(text, min_chars=80)
        assert len(claims) == 1
        assert "much longer" in claims[0]


class TestParseLabelBlock:
    def test_supported(self):
        raw = (
            "LABEL: SUPPORTED\n"
            "EVIDENCE: \"NUMT filtering is mandatory\"\n"
            "CITEKEY: @smith2024\n"
            "NOTE: none"
        )
        parsed = _parse_label_block(raw)
        assert parsed["LABEL"] == "SUPPORTED"
        assert "mandatory" in parsed["EVIDENCE"]
        assert parsed["CITEKEY"] == "@smith2024"
        assert parsed["NOTE"] == "none"

    def test_unsupported_default(self):
        # Missing fields fall back to defaults.
        parsed = _parse_label_block("LABEL: UNSUPPORTED")
        assert parsed["LABEL"] == "UNSUPPORTED"
        assert parsed["EVIDENCE"] == "none"
        assert parsed["CITEKEY"] == "none"

    def test_case_insensitive_keys(self):
        parsed = _parse_label_block("label: PARTIAL\nevidence: short quote\nCITEKEY: @x\nnote: weak match")
        assert parsed["LABEL"] == "PARTIAL"
        assert parsed["EVIDENCE"] == "short quote"
        assert parsed["NOTE"] == "weak match"
