"""Tests for quick_ai_score.py — mechanical AI text detection."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from quick_ai_score import (
    score_text,
    _sentences,
    _paragraphs,
    _check_em_dashes,
    _check_sentence_length,
    _check_comma_density,
    _check_burstiness,
    _check_formulaic_phrases,
    _check_paragraph_openings,
    _check_roadmap_sentences,
)


HUMAN_PROSE = "Molecular dynamics simulations generate ensembles of protein conformations. These ensembles can reveal transient binding pockets not visible in static crystal structures. Identifying these pockets remains a computational challenge."

AI_PROSE = "This paper presents a comprehensive analysis of the intricate interplay between molecular dynamics simulations and protein conformations. Moreover, it is crucial to highlight the pivotal role of robust computational frameworks. Furthermore, the results underscore the groundbreaking nature of these findings, which shed light on the complex dynamics. Additionally, the approach leverages synergistic interactions. Taken together, these observations pave the way for future research. In conclusion, this study opens new avenues for investigation."

EM_DASH_PROSE = "The pipeline processes data in three stages—parsing, clustering, and ranking—before output. This approach—while effective—has limitations."

LONG_SENTENCES = "The computational pipeline described in this paper integrates trajectory parsing with geometry-based pocket detection using a modified version of the p2rank algorithm that assigns per-residue binding probabilities to each putative site, and these probabilities are then used as feature vectors for density-based clustering across simulation frames with an automatically tuned DBSCAN implementation that maximizes the silhouette coefficient over a grid of candidate hyperparameters."

MANY_COMMAS = "First, we parse the trajectory, then we detect pockets, then we cluster them, then we rank them, and finally we output the results."

ROADMAP = "This paper is organized as follows. The next section describes the methods in detail. The subsequent sections report the results, discuss the findings, and conclude with future directions."


class TestSentences:
    def test_basic(self):
        s = _sentences("The quick brown fox. Jumps over the lazy dog.")
        assert len(s) == 2
        assert s[0] == "The quick brown fox."
        assert s[1] == "Jumps over the lazy dog."

    def test_skips_very_short(self):
        s = _sentences("Hi. This is a complete sentence with more words. No.")
        # "Hi." (2 words) and "No." (1 word) should be skipped
        assert len(s) == 1
        assert "complete" in s[0]


class TestParagraphs:
    def test_basic(self):
        text = "First paragraph with enough words to be valid for testing purposes.\n\nSecond paragraph also with enough words to be valid for the test."
        p = _paragraphs(text)
        assert len(p) == 2

    def test_skips_short(self):
        text = "Short.\n\nA proper paragraph with enough words to qualify as a real paragraph for testing purposes."
        p = _paragraphs(text)
        assert len(p) == 1


class TestEmDashCheck:
    def test_clean_text(self):
        result = _check_em_dashes(HUMAN_PROSE)
        assert result["em_dash_count"] == 0
        assert result["verdict"] == "clean"

    def test_em_dashes_flag_ai(self):
        result = _check_em_dashes(EM_DASH_PROSE)
        assert result["em_dash_count"] >= 2
        assert result["verdict"] in ("warning", "ai-like")

    def test_ignores_markdown_tables(self):
        table_text = "|------|------|\n| A | B |\n| C | D |"
        result = _check_em_dashes(table_text)
        assert result["em_dash_count"] == 0

    def test_ignores_code_blocks(self):
        code_text = "```\n---\n---\n```\nNormal text here."
        result = _check_em_dashes(code_text)
        assert result["em_dash_count"] == 0


class TestSentenceLengthCheck:
    def test_short_sentences(self):
        sentences = _sentences(HUMAN_PROSE)
        result = _check_sentence_length(sentences)
        assert result["over_35_words"] == 0
        assert result["verdict"] == "clean"

    def test_long_sentences_flag(self):
        sentences = _sentences(LONG_SENTENCES)
        result = _check_sentence_length(sentences)
        assert result["over_50_words"] >= 1
        assert result["verdict"] in ("warning", "ai-like")


class TestCommaDensityCheck:
    def test_normal_commas(self):
        sentences = _sentences(HUMAN_PROSE)
        result = _check_comma_density(sentences)
        assert result["score"] < 3

    def test_many_commas_flag(self):
        sentences = _sentences(MANY_COMMAS)
        result = _check_comma_density(sentences)
        assert result["sentences_with_4plus_commas"] >= 1


class TestBurstinessCheck:
    def test_varied_lengths_human(self):
        text = "This is a short sentence. But this one is much longer and contains more words to make the point clear. And here a third."
        sentences = _sentences(text)
        result = _check_burstiness(sentences)
        assert result["coefficient_of_variation"] > 0.3

    def test_uniform_lengths_ai(self):
        text = ("This is a sentence with exactly seven. "
                "Another sentence with exactly seven. "
                "Yet another sentence with exactly seven. "
                "Finally one more with exactly seven.")
        sentences = _sentences(text)
        result = _check_burstiness(sentences)
        assert result["coefficient_of_variation"] < 0.4


class TestFormulaicPhrases:
    def test_clean_text(self):
        result = _check_formulaic_phrases(HUMAN_PROSE, [], [], [])
        assert result["total_formulaic_hits"] == 0
        assert result["verdict"] == "clean"

    def test_detects_ai_words(self):
        ai_words = ["delve", "crucial", "robust", "pivotal", "groundbreaking",
                     "comprehensive", "moreover", "furthermore", "notably",
                     "underscores", "highlights", "sheds light",
                     "additionally", "taken together", "in conclusion",
                     "opens new avenues"]
        result = _check_formulaic_phrases(AI_PROSE, ai_words, [], [])
        assert result["total_formulaic_hits"] >= 5

    def test_detects_structures(self):
        structures = [r"not only .{1,30} but also", r"in conclusion"]
        result = _check_formulaic_phrases(AI_PROSE, [], structures, [])
        assert result["total_formulaic_hits"] >= 1


class TestParagraphOpenings:
    def test_varied_openings(self):
        text = ("\n\n".join([
            "The first paragraph contains important context for the analysis.",
            "Our approach uses a novel computational method for detection.",
            "These results demonstrate that the method outperforms baselines.",
            "Future work should extend the method to additional datasets.",
        ]))
        paragraphs = _paragraphs(text)
        result = _check_paragraph_openings(paragraphs)
        assert result["verdict"] == "clean"

    def test_repeated_openings_flag(self):
        text = ("\n\n".join([
            "The pipeline processes input data efficiently for the analysis task.",
            "The pipeline processes input data efficiently for the clustering step.",
            "The pipeline processes input data efficiently for the ranking module.",
            "The pipeline processes input data efficiently for the output display.",
        ]))
        paragraphs = _paragraphs(text)
        result = _check_paragraph_openings(paragraphs)
        assert result["verdict"] in ("warning", "ai-like")


class TestRoadmapSentences:
    def test_no_roadmap(self):
        result = _check_roadmap_sentences(HUMAN_PROSE)
        assert result["roadmap_count"] == 0
        assert result["verdict"] == "clean"

    def test_detects_roadmap(self):
        result = _check_roadmap_sentences(ROADMAP)
        assert result["roadmap_count"] >= 1
        assert result["verdict"] in ("warning", "ai-like")


class TestOverallScoring:
    def test_human_text_scores_low(self):
        result = score_text(HUMAN_PROSE)
        assert result["overall_score"] < 5
        assert result["verdict"] in ("human-like", "mostly human")

    def test_ai_text_scores_high(self):
        result = score_text(AI_PROSE + " " + EM_DASH_PROSE)
        assert result["overall_score"] > 3

    def test_returns_all_checks(self):
        result = score_text(HUMAN_PROSE)
        expected_checks = {"em_dashes", "sentence_length", "comma_density",
                           "burstiness", "formulaic_phrases", "paragraph_openings",
                           "roadmap_sentences"}
        assert set(result["checks"].keys()) == expected_checks

    def test_json_output(self):
        result = score_text(HUMAN_PROSE)
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert parsed["overall_score"] == result["overall_score"]
