"""Tests for outline_recommender.py — paper-type templates, prompt builders,
evidence mapping, and CLI validation. No network / LLM calls (model is
monkeypatched; the retriever is a fake)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))

from research_assistant.writing import outline_recommender as orec


class TestPaperTypes:
    def test_registry_not_empty_and_has_core_types(self):
        for key in ("imrad", "review", "systematic-review", "thesis-chapter",
                    "methods", "case-study"):
            assert key in orec.PAPER_TYPES, f"missing paper type {key}"

    def test_every_type_has_sections_with_valid_shares(self):
        for key, ptype in orec.PAPER_TYPES.items():
            assert ptype.sections, f"{key} has no sections"
            total = sum(s.share for s in ptype.sections)
            # Shares should sum to ~1.0 so word estimates are meaningful.
            assert abs(total - 1.0) < 0.01, f"{key} shares sum to {total}"
            for s in ptype.sections:
                assert s.name.strip()
                assert s.purpose.strip()
                assert 0 < s.share <= 1.0

    def test_label_present(self):
        for ptype in orec.PAPER_TYPES.values():
            assert ptype.label.strip()


class TestEstimateWords:
    def test_basic(self):
        assert orec.estimate_words(8000, 0.25) == 2000

    def test_rounds_to_nearest_fifty(self):
        # 8000 * 0.13 = 1040 -> rounded to 1050
        assert orec.estimate_words(8000, 0.13) % 50 == 0

    def test_zero_total(self):
        assert orec.estimate_words(0, 0.25) == 0


class TestBuildStructurePrompt:
    def test_contains_topic_and_sections(self):
        p = orec.build_structure_prompt(
            topic="NUMT contamination in clinical mtDNA",
            paper_type_key="imrad",
            discipline="bioinformatics",
            audience="domain experts",
            target_words=6000,
        )
        assert "NUMT contamination in clinical mtDNA" in p
        assert "bioinformatics" in p
        # canonical IMRaD sections should be seeded into the prompt
        assert "Introduction" in p
        assert "Methods" in p
        # note-taking contract is preserved (no polished prose)
        assert "needs evidence" in p.lower()

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError):
            orec.build_structure_prompt(
                topic="x", paper_type_key="not-a-type",
                discipline="", audience="", target_words=4000,
            )

    def test_includes_word_estimates_when_target_given(self):
        p = orec.build_structure_prompt(
            topic="x", paper_type_key="imrad",
            discipline="", audience="", target_words=8000,
        )
        assert "words" in p.lower()


class TestBuildVariantsPrompt:
    def test_asks_for_alternatives(self):
        p = orec.build_variants_prompt(
            topic="CRISPR delivery methods",
            paper_type_key="review",
            discipline="molecular biology",
        )
        assert "CRISPR delivery methods" in p
        # should request multiple organizational schemes
        assert "thematic" in p.lower() or "organization" in p.lower() \
            or "organisation" in p.lower()


class _FakeRetriever:
    """Return canned chunks per query substring for evidence-map tests."""

    def __init__(self, mapping: dict[str, list[str]]):
        self._mapping = mapping

    def __call__(self, query: str, **_):
        for needle, citekeys in self._mapping.items():
            if needle.lower() in query.lower():
                return [
                    {"metadata": {"citekey": ck}, "similarity": 0.9}
                    for ck in citekeys
                ]
        return []


class TestEvidenceMap:
    def test_maps_citekeys_per_section_and_flags_gaps(self):
        retr = _FakeRetriever({"Introduction": ["smith2024", "jones2023"]})
        emap = orec.build_evidence_map(
            topic="anything",
            paper_type_key="imrad",
            retriever=retr,
        )
        # Every canonical section appears as a key
        names = [s.name for s in orec.PAPER_TYPES["imrad"].sections]
        assert set(emap.keys()) == set(names)
        assert emap["Introduction"] == ["smith2024", "jones2023"]
        # A section with no matching chunks is an empty list (a gap)
        gap_sections = [n for n, cks in emap.items() if not cks]
        assert gap_sections  # at least one gap given the fake

    def test_dedupes_citekeys_preserving_order(self):
        retr = _FakeRetriever({"Introduction": ["a", "b", "a", "c", "b"]})
        emap = orec.build_evidence_map("t", "imrad", retriever=retr)
        assert emap["Introduction"] == ["a", "b", "c"]

    def test_render_coverage_lists_sources_and_gaps(self):
        emap = {"Introduction": ["smith2024"], "Methods": []}
        md = orec.render_evidence_coverage(emap)
        assert "Introduction" in md
        assert "smith2024" in md
        assert "Methods" in md
        # gap marker present for the empty section
        assert "gap" in md.lower()


class TestCli:
    def test_rejects_unknown_paper_type(self):
        result = CliRunner().invoke(orec.main, ["topic here", "--paper-type", "bogus"])
        assert result.exit_code != 0

    def test_rejects_blank_topic(self):
        result = CliRunner().invoke(orec.main, ["   "])
        assert result.exit_code != 0

    def test_rejects_out_of_range_target_words(self):
        result = CliRunner().invoke(
            orec.main, ["topic", "--target-words", "10"]
        )
        assert result.exit_code != 0

    def test_happy_path_calls_model(self, monkeypatch):
        calls = {}

        def fake_ask_model(prompt, **kwargs):
            calls["prompt"] = prompt
            return {"text": "## Introduction\n- stub", "input_tokens": 10,
                    "output_tokens": 20, "cost": 0.01}

        monkeypatch.setattr(orec, "ask_model", fake_ask_model)
        result = CliRunner().invoke(
            orec.main,
            ["NUMT contamination", "--paper-type", "imrad", "--raw"],
        )
        assert result.exit_code == 0, result.output
        assert "Introduction" in result.output
        assert "NUMT contamination" in calls["prompt"]

    def test_variants_flag_triggers_second_call(self, monkeypatch):
        prompts = []

        def fake_ask_model(prompt, **kwargs):
            prompts.append(prompt)
            return {"text": "result", "input_tokens": 1, "output_tokens": 1,
                    "cost": 0.0}

        monkeypatch.setattr(orec, "ask_model", fake_ask_model)
        result = CliRunner().invoke(
            orec.main,
            ["topic", "--paper-type", "review", "--variants", "--raw"],
        )
        assert result.exit_code == 0, result.output
        assert len(prompts) == 2  # structure + variants
