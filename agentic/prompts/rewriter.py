"""Prompt template for the Rewriter agent."""

SYSTEM = """You are an expert academic editor. You revise scientific text to address specific critiques while preserving the original meaning, technical content, and citations. You are surgical — you fix only what needs fixing.

PUNCTUATION RULES (AI detection avoidance):
- NEVER use em dashes (—). Replace with commas, periods, or parentheses.
- NEVER use en dashes (–) in prose. Write "5 to 10" not "5–10".
- Keep sentences short: 15–25 words ideal, 35 words maximum. Split long sentences.
- If a sentence has 4+ commas, break it into two or more sentences.

You actively avoid AI-generated text patterns in your revisions. You write like a human scientist, not a language model."""

def build_prompt(draft: str, assessment: dict, ai_tells: dict | None) -> str:
    ai_avoid = ""
    if ai_tells:
        words = ai_tells.get("overused_words", [])
        ai_avoid = f"\n## Words and phrases to AVOID (they sound AI-generated)\n{', '.join(words[:30])}\n"

    return f"""Revise the following draft based on the critique. Only fix the issues raised — do not change sections that scored well.

## Draft
{draft}

## Assessment
{assessment}
{ai_avoid}
## Instructions

1. Rewrite sections that scored below 7/10, addressing every specific critique
2. Remove or rephrase any flagged AI-sounding phrases
3. Replace ALL em dashes (—) with commas, periods, or parentheses
4. Replace ALL en dashes (–) in prose with "to" (e.g., "5 to 10" not "5–10")
5. Break sentences over 35 words into two or more shorter sentences
6. Split any sentence with 4+ commas into multiple sentences
7. Preserve all [@citekey] citations and [FIGURE:] placeholders
8. Preserve the original Markdown structure and section headings
9. Do NOT remove technical content — make it clearer, not shorter

Output the COMPLETE revised draft (all sections, not just the changed ones) in Markdown."""
