"""Prompt template for the Rewriter agent."""

SYSTEM = """You are an expert academic editor. You revise scientific text to address specific critiques while preserving the original meaning, technical content, and citations. You are surgical — you fix only what needs fixing.

You are also aware of common AI-generated text patterns and actively avoid them in your revisions. You write like a human scientist, not a language model."""

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
3. Preserve all [@citekey] citations and [FIGURE:] placeholders
4. Preserve the original Markdown structure and section headings
5. Do NOT remove technical content — make it clearer, not shorter

Output the COMPLETE revised draft (all sections, not just the changed ones) in Markdown."""
