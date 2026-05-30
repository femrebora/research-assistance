"""text_cleanup.py — mechanical post-processing to fix AI-sounding prose.

Applied after Writer and Rewriter produce text. Removes em dashes,
splits overlong sentences, fixes en dashes. Pure mechanical — no LLM calls.
"""
from __future__ import annotations

import re

# Conjunction break points: split BEFORE these (keeping them with the second clause)
BREAK_BEFORE = re.compile(
    r"\s+(?=(?:which|while|where|whereas|although|though|because|since|unless|"
    r"whereby|wherein|whereupon)\s)",
    re.IGNORECASE,
)

# Split AFTER these coordination words at clause boundaries
BREAK_AFTER = re.compile(
    r"(?<=[,;])\s+(?=(?:and|but|or|yet|so|thus|therefore|hence|however|"
    r"moreover|furthermore|consequently|accordingly)\s)",
    re.IGNORECASE,
)

# For sentences with many commas, split at the middle comma group
COMMA_SPLIT = re.compile(r",\s+(?=(?:which|thereby|thus|resulting|leading|"
                          r"allowing|enabling|providing|yielding)\s)", re.IGNORECASE)

# Em dash patterns to replace
EM_DASH = re.compile(r"\s*---?\s*|\s*—\s*")

# En dash in text ranges (not tables)
EN_DASH_RANGE = re.compile(r"(\d+)\s*[–-]\s*(\d+)")

# Sentences that start with a lowercase letter after splitting need capitalization
LOWERCASE_START = re.compile(r"^([a-z])")


def _is_markdown_heading(line: str) -> bool:
    """Check if a line is a markdown heading or horizontal rule."""
    return bool(re.match(r"^#{1,6}\s", line) or re.match(r"^[-*_]{3,}\s*$", line))


def split_long_sentences(text: str, max_words: int = 35) -> str:
    """Split sentences over max_words at natural break points.

    Paragraph-aware: preserves markdown headings, blank lines, code blocks,
    and paragraph structure. Only splits within prose paragraphs.
    """
    # Split into markdown blocks (paragraphs, headings, code fences)
    blocks = re.split(r"(\n{2,})", text)
    result_parts = []

    for block in blocks:
        if not block.strip():
            result_parts.append(block)
            continue

        # Preserve blank-line separators as-is
        if re.match(r"^\n{2,}$", block):
            result_parts.append(block)
            continue

        stripped = block.strip()

        # Preserve code blocks
        if stripped.startswith("```"):
            result_parts.append(block)
            continue

        # Preserve markdown headings
        if _is_markdown_heading(stripped):
            result_parts.append(block)
            continue

        # Preserve table rows and list items
        if re.match(r"^\s*[\|\-\*\+]", stripped):
            result_parts.append(block)
            continue

        # Prose paragraph: split into sentences and process
        # Negative lookbehinds prevent splitting on abbreviations (e.g., i.e., et al., Fig.)
        sentences = re.split(
            r"(?<=[.!?])(?<!e\.g\.)(?<!i\.e\.)(?<!al\.)(?<!Fig\.)(?<!Eq\.)\s+",
            stripped,
        )
        processed = []
        for s in sentences:
            words = s.split()
            if len(words) <= max_words:
                processed.append(s)
                continue
            parts = _split_one_sentence(s, max_words)
            processed.extend(parts)

        result_parts.append(" ".join(processed))

    return "".join(result_parts)


def _split_one_sentence(sentence: str, max_words: int) -> list[str]:
    """Attempt to split one sentence into parts. Returns list of sentence strings."""
    parts = [sentence]
    safety = 0

    while safety < 10:
        safety += 1
        new_parts = []
        changed = False

        for part in parts:
            words = part.split()
            if len(words) <= max_words:
                new_parts.append(part)
                continue

            split_result = _try_split(part)
            if split_result and len(split_result) > 1:
                new_parts.extend(split_result)
                changed = True
            else:
                new_parts.append(part)

        parts = new_parts
        if not changed:
            break

    return parts


def _try_split(sentence: str) -> list[str] | None:
    """Try to split a sentence at a natural break. Returns None if no good split."""
    # Try break-before conjunctions
    match = BREAK_BEFORE.search(sentence)
    if match and _is_safe_split(sentence, match.start()):
        left = sentence[:match.start()].rstrip()
        right = sentence[match.start():].lstrip()
        right = _capitalize(right)
        if len(left.split()) >= 10 and len(right.split()) >= 8:
            return [left + ".", right]

    # Try break-after at comma+conjunction
    for m in BREAK_AFTER.finditer(sentence):
        if _is_safe_split(sentence, m.start()):
            left = sentence[:m.start()].rstrip().rstrip(",")
            right = sentence[m.end():].lstrip()
            right = _capitalize(right)
            if len(left.split()) >= 10 and len(right.split()) >= 8:
                return [left + ".", right]
            break

    # Try middle-comma split for long sentences
    words = sentence.split()
    comma_count = sentence.count(",")
    if comma_count >= 4 and len(words) > 40:
        comma_positions = [i for i, c in enumerate(sentence) if c == ","]
        if len(comma_positions) >= 2:
            mid = comma_positions[len(comma_positions) // 2]
            if _is_safe_split(sentence, mid + 1):
                left = sentence[:mid].rstrip()
                right = sentence[mid + 1:].lstrip()
                right = _capitalize(right)
                if len(left.split()) >= 12 and len(right.split()) >= 10:
                    return [left + ".", right]

    return None


def _is_safe_split(text: str, pos: int) -> bool:
    """Check that splitting at pos won't break a citation or code block."""
    # Don't split inside a [@citekey] or [FIGURE:] marker
    before = text[:pos]
    after = text[pos:]

    open_br = before.count("[") - before.count("]")
    open_paren = before.count("(") - before.count(")")
    close_br = after.count("]") - after.count("[")

    # If we're inside brackets or parens, don't split
    return open_br <= 0 and open_paren <= 0 and close_br <= 0


def _capitalize(text: str) -> str:
    """Capitalize the first letter of text."""
    return LOWERCASE_START.sub(lambda m: m.group(1).upper(), text.strip())


def remove_em_dashes(text: str) -> str:
    """Replace em dashes with commas or periods."""
    # Count em dashes at sentence boundaries (preceded by a complete thought)
    # Replace with period+space when it's a clause break, comma otherwise
    text = EM_DASH.sub(_em_dash_replacement, text)
    return text


def _em_dash_replacement(match: re.Match) -> str:
    """Pick comma or period for em dash based on context."""
    full = match.string
    pos = match.start()

    # Look at preceding/following chars
    before = full[max(0, pos - 120):pos]

    # If preceding text looks like a complete clause, use period. Otherwise comma.
    before_words = len(before.split())
    if before_words > 12:
        return ". "
    return ", "


def replace_en_dashes(text: str) -> str:
    """Replace en dashes in numeric ranges with 'to'."""
    return EN_DASH_RANGE.sub(r"\1 to \2", text)


def cleanup_prose(text: str, max_words: int = 35) -> str:
    """Run all mechanical cleanup on a paper draft.

    Returns cleaned text with em dashes removed, en dashes replaced,
    and long sentences split.
    """
    text = remove_em_dashes(text)
    text = replace_en_dashes(text)
    text = split_long_sentences(text, max_words=max_words)
    return text
