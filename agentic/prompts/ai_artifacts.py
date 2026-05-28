"""Prompt template for the AI Artifact Detector agent."""

SYSTEM = """You research how AI language models write, identifying the specific words, phrases, and sentence structures that make AI-generated text detectable. You are an expert in AI-text forensics."""

def build_prompt() -> str:
    return """Research the current state of AI-generated text detection (as of mid-2026). Based on what you know about how LLMs write, compile a comprehensive list of AI text artifacts.

Produce a structured JSON document with these categories:

## 1. Overused Words
Words that AI models use disproportionately compared to human academic writers.

## 2. Formulaic Structures
Sentence templates that AI models reuse across different contexts.

## 3. Hedging Overuse Patterns
Ways AI models hedge claims excessively.

## 4. AI Sentence Patterns
Full-sentence patterns that are characteristic of AI writing.

## 5. Stylistic Uniformity Markers
Features that make AI text feel uniform: sentence length patterns, paragraph structure, argument flow.

For each category, include specific examples. Make this a practical detection guide.

Output ONLY valid JSON (no markdown fences):

{
  "overused_words": ["word1", "word2", ...],
  "formulaic_structures": ["structure1", "structure2", ...],
  "hedging_overuse": ["pattern1", "pattern2", ...],
  "ai_sentence_patterns": ["pattern1", ...],
  "stylistic_uniformity_markers": ["marker1", ...],
  "last_updated": "YYYY-MM-DD",
  "notes": "Brief note about sources/methodology"
}
"""
