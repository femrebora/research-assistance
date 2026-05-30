"""Prompt template for the Plagiarism + AI Checker agent."""

SYSTEM = """You are a plagiarism and AI-text detection expert. You analyze academic text for originality. You know the linguistic fingerprints of AI-generated text: formulaic structures, overuse of certain transitions, uniform sentence lengths, lack of authentic voice, and generic hedging patterns.

You give honest, calibrated scores. A score above 80% originality means the text reads as genuinely human-written academic work."""

def build_prompt(text: str, ai_tells: dict | None) -> str:
    ai_ref = ""
    if ai_tells:
        words = ai_tells.get("overused_words", [])
        structures = ai_tells.get("formulaic_structures", [])
        ai_ref = f"""
## Known AI Text Markers
Overused AI words: {', '.join(words[:25])}
Formulaic AI structures: {'; '.join(structures[:10])}
"""

    return f"""Analyze the following academic text for originality and AI-generated patterns.

{ai_ref}

## Text to Analyze
{text[:8000]}

## Your Task

1. **Originality Score (0–100%)**: Estimate how original this text is. Consider:
   - Does it express ideas in fresh, specific language? (high originality)
   - Does it use generic, formulaic descriptions? (low originality)
   - Are there specific technical details that feel genuinely observed, not generated?

2. **AI-Likelihood Score (0–100%)**: Estimate the probability this was written by AI. Consider:
   - Frequency of known AI-favored words and structures
   - Sentence length uniformity (AI tends toward uniform lengths)
   - Presence of authentic voice, unexpected phrasings, or personal perspective (human markers)
   - Overuse of hedging and "both sides" framing

3. **Flagged Passages**: List any specific sentences or phrases that strongly indicate AI authorship.

## Output Format
Output ONLY valid JSON (no markdown fences):

{{
  "originality_pct": N,
  "ai_likelihood_pct": N,
  "flagged_passages": ["passage 1", "passage 2"],
  "notes": "Brief overall assessment"
}}
"""
