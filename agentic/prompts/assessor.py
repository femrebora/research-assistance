"""Prompt template for the Assessor agent."""

SYSTEM = """You are a rigorous academic reviewer for a top-tier bioinformatics journal. You evaluate paper drafts for scientific quality, clarity, and originality. You give honest, specific feedback with numerical scores.

Additionally, you have been trained to detect AI-generated text artifacts. You know the common tells: overused transition phrases, formulaic sentence structures, excessive hedging, and GPT-isms. You flag these when you see them."""

def build_prompt(draft: str, ai_tells: dict | None) -> str:
    ai_tells_str = ""
    if ai_tells:
        words = ai_tells.get("overused_words", [])
        structures = ai_tells.get("formulaic_structures", [])
        patterns = ai_tells.get("ai_sentence_patterns", [])

        ai_tells_str = f"""
## AI Text Artifacts to Watch For
Overused AI words: {', '.join(words[:20])}
Formulaic structures: {'; '.join(structures[:10])}
Common AI patterns: {'; '.join(patterns[:10])}
"""

    return f"""Evaluate the following academic paper draft. Score each section and flag issues.

{ai_tells_str}

## Draft
{draft}

## Your Task

For each of these sections present in the draft, score 1–10:
- **Abstract**: clarity, completeness, whether it states the contribution
- **Introduction**: problem framing, literature context, clear contribution statement
- **Methods**: algorithmic detail, reproducibility, parameter specification
- **Results**: data presentation, benchmark quality, figure descriptions
- **Discussion**: interpretation depth, limitation acknowledgment, future work

For each section also score:
- **AI-sounding** (1–10): 1 = reads naturally human, 10 = obvious AI-generated text. Flag specific phrases that sound AI-generated.

## Output Format

Output ONLY valid JSON (no markdown fences, no other text):

{{
  "abstract": {{"score": N, "ai_score": N, "critique": "...", "ai_phrases": ["..."]}},
  "introduction": {{"score": N, "ai_score": N, "critique": "...", "ai_phrases": ["..."]}},
  "methods": {{"score": N, "ai_score": N, "critique": "...", "ai_phrases": ["..."]}},
  "results": {{"score": N, "ai_score": N, "critique": "...", "ai_phrases": ["..."]}},
  "discussion": {{"score": N, "ai_score": N, "critique": "...", "ai_phrases": ["..."]}},
  "overall_notes": "..."
}}

Only include sections that actually exist in the draft. Use the exact keys shown."""
