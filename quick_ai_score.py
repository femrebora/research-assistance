#!/usr/bin/env python3
"""quick_ai_score.py — mechanical AI-text detection without LLM calls.

Checks em dashes, sentence length, comma density, formulaic phrases,
paragraph openings, and burstiness. Scores from 0 (human-like) to 10 (obvious AI).

Usage:
    ./quick_ai_score.py paper.md
    ./quick_ai_score.py paper.md --json
    ./quick_ai_score.py paper.md --ai-tells ~/thesis/cache/ai_tells.json
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import click

# ── Default AI tells ────────────────────────────────────────────────────────

DEFAULT_AI_WORDS = [
    "delve", "crucial", "robust", "moreover", "furthermore", "consequently",
    "notably", "intricate", "paramount", "pivotal", "comprehensive",
    "holistic", "cutting-edge", "state-of-the-art", "groundbreaking",
    "additionally", "underscores", "highlights", "sheds light",
    "game changer", "revolutionize", "disruptive", "synergistic",
    "leverage", "ecosystem", "actionable", "scalable", "seamless",
    "robustly", "significantly", "substantially", "remarkably",
]

DEFAULT_AI_STRUCTURES = [
    r"not only .{1,30} but also",
    r"on the (?:one|other) hand",
    r"it is (?:important|worth|essential|necessary|crucial) to",
    r"plays? a (?:crucial|key|vital|pivotal|essential|important) role",
    r"in the context of",
    r"a testament to",
    r"at the heart of",
    r"paves the way",
    r"bridge the gap",
    r"in conclusion",
    r"as such",
    r"consistent with",
    r"taken together",
    r"opens new avenues",
    r"paves the way for",
    r"poised to",
]

DEFAULT_AI_SENTENCE_PATTERNS = [
    r"^The (?:pipeline|approach|method|system|framework|tool) ",
    r"^This (?:approach|method|system|framework|pipeline|tool) ",
    r"^These (?:results|findings|observations|data) ",
    r"^In (?:this|our|the) (?:study|work|paper|article|research|investigation)",
    r"^Our (?:results|findings|analysis|approach|method|work) ",
]


# ── Sentence splitting ──────────────────────────────────────────────────────

def _sentences(text: str) -> list[str]:
    """Split text into sentences, keeping them reasonably intact."""
    raw = re.split(r"(?<=[.!?])\s+", text)
    cleaned = []
    for s in raw:
        s = s.strip()
        if s and len(s.split()) >= 3:
            cleaned.append(s)
    return cleaned


def _paragraphs(text: str) -> list[str]:
    """Split text into paragraphs."""
    blocks = re.split(r"\n\s*\n", text)
    return [b.strip() for b in blocks if len(b.split()) >= 10]


# ── Individual checks ───────────────────────────────────────────────────────

def _check_em_dashes(text: str) -> dict:
    """Count em dashes and en dashes."""
    # Strip code blocks, markdown tables, and HRs to avoid false positives
    cleaned = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"`[^`]+`", "", cleaned)
    cleaned = re.sub(r"^---\s*$", "", cleaned, flags=re.MULTILINE)
    # Strip markdown table rows (dash-heavy lines with pipes)
    cleaned = re.sub(r"^\s*\|[\s\-:|]+\|\s*$", "", cleaned, flags=re.MULTILINE)
    em_count = cleaned.count("—") + cleaned.count("---")
    en_count = cleaned.count("–")
    words = len(text.split())

    # Score: 0 em dashes = 0, 1+ per 500 words = penalty
    em_per_1k = (em_count / max(words, 1)) * 1000
    en_per_1k = (en_count / max(words, 1)) * 1000

    # Humans rarely use em dashes in academic writing
    score = min(10, em_per_1k * 20 + en_per_1k * 5)

    return {
        "em_dash_count": em_count,
        "en_dash_count": en_count,
        "score": round(score, 1),
        "verdict": "clean" if score < 1 else "warning" if score < 3 else "ai-like",
    }


def _check_sentence_length(sentences: list[str]) -> dict:
    """Analyze sentence length distribution."""
    if not sentences:
        return {"score": 0, "verdict": "clean"}

    lengths = [len(s.split()) for s in sentences]
    avg_len = sum(lengths) / len(lengths)
    max_len = max(lengths)
    over_35 = sum(1 for n in lengths if n > 35)
    over_50 = sum(1 for n in lengths if n > 50)
    pct_over_35 = over_35 / len(lengths) * 100

    # Humans vary sentence length. AI tends toward uniform medium-long.
    # Penalize: avg > 28, many over 35, any over 50
    score = 0.0
    score += max(0, (avg_len - 20) * 0.3)
    score += pct_over_35 * 0.2
    score += over_50 * 2
    score = min(10, score)

    return {
        "sentence_count": len(sentences),
        "avg_words": round(avg_len, 1),
        "max_words": max_len,
        "over_35_words": over_35,
        "over_50_words": over_50,
        "score": round(score, 1),
        "verdict": "clean" if score < 2 else "warning" if score < 4 else "ai-like",
    }


def _check_comma_density(sentences: list[str]) -> dict:
    """Detect sentences overloaded with commas."""
    if not sentences:
        return {"score": 0, "verdict": "clean"}

    high_comma = 0
    for s in sentences:
        commas = s.count(",")
        if commas >= 4:
            high_comma += 1

    pct = high_comma / len(sentences) * 100
    score = min(10, pct * 0.5)

    return {
        "sentences_with_4plus_commas": high_comma,
        "pct_of_total": round(pct, 1),
        "score": round(score, 1),
        "verdict": "clean" if score < 2 else "warning" if score < 4 else "ai-like",
    }


def _check_burstiness(sentences: list[str]) -> dict:
    """Measure sentence length variation (burstiness).

    Human writing shows high variance — short punchy sentences mixed with long ones.
    AI writing has low variance — sentences cluster around the same length.
    """
    if len(sentences) < 3:
        return {"score": 0, "verdict": "clean"}

    lengths = [len(s.split()) for s in sentences]

    # Coefficient of variation
    mean_len = sum(lengths) / len(lengths)
    if mean_len == 0:
        return {"score": 10, "verdict": "ai-like"}

    variance = sum((n - mean_len) ** 2 for n in lengths) / len(lengths)
    std_dev = variance ** 0.5
    cv = std_dev / mean_len

    # Adjacent length differences (burstiness proper)
    diffs = [abs(lengths[i] - lengths[i - 1]) for i in range(1, len(lengths))]
    avg_diff = sum(diffs) / len(diffs)

    # High CV + high avg_diff = human. Low = AI.
    # CV < 0.3 is suspicious, CV > 0.6 is human-like
    cv_score = max(0, (0.6 - cv) * 15)
    diff_score = max(0, (8 - avg_diff) * 1.2)
    score = min(10, (cv_score + diff_score) / 2)

    return {
        "coefficient_of_variation": round(cv, 3),
        "avg_adjacent_diff": round(avg_diff, 1),
        "interpretation": (
            "high variance (human-like)" if cv > 0.6
            else "moderate variance" if cv > 0.4
            else "low variance (AI-like)" if cv > 0.25
            else "very low variance (strong AI signal)"
        ),
        "score": round(score, 1),
        "verdict": "clean" if score < 3 else "warning" if score < 5 else "ai-like",
    }


def _check_formulaic_phrases(text: str, ai_words: list[str],
                              ai_structures: list[str],
                              ai_patterns: list[str]) -> dict:
    """Count occurrences of known AI tells."""
    text_lower = text.lower()
    words_in_text = len(text.split())

    # Word hits
    word_hits = {}
    for w in ai_words:
        count = len(re.findall(r"\b" + re.escape(w) + r"\b", text_lower))
        if count:
            word_hits[w] = count

    # Structure hits
    structure_hits = {}
    for pat in ai_structures:
        matches = re.findall(pat, text_lower)
        if matches:
            structure_hits[pat] = len(matches)

    # Sentence pattern hits
    sentences = _sentences(text)
    pattern_hits = {}
    for pat in ai_patterns:
        count = sum(1 for s in sentences if re.search(pat, s, re.IGNORECASE))
        if count:
            pattern_hits[pat] = count

    total_hits = sum(word_hits.values()) + sum(structure_hits.values()) + sum(pattern_hits.values())
    hits_per_1k = (total_hits / max(words_in_text, 1)) * 1000

    score = min(10, hits_per_1k * 1.5)

    return {
        "total_formulaic_hits": total_hits,
        "hits_per_1000_words": round(hits_per_1k, 1),
        "word_hits": word_hits,
        "structure_hits": structure_hits,
        "pattern_hits": pattern_hits,
        "score": round(score, 1),
        "verdict": "clean" if score < 2 else "warning" if score < 4 else "ai-like",
    }


def _check_paragraph_openings(paragraphs: list[str]) -> dict:
    """Check for repetitive paragraph openings — a strong AI tell."""
    if len(paragraphs) < 3:
        return {"score": 0, "verdict": "clean"}

    openings = []
    for p in paragraphs:
        first_sentence = re.split(r"(?<=[.!?])\s+", p.strip())[0]
        # Get first 3 words
        first_words = " ".join(first_sentence.split()[:3]).lower()
        openings.append(first_words)

    # Count duplicate openings
    counts = Counter(openings)
    dupes = {k: v for k, v in counts.items() if v > 1}
    max_repeat = max(counts.values()) if counts else 1

    # Score based on repetition (only flag if >2 repeats or >3 dupes)
    if max_repeat <= 2 and len(dupes) <= 3:
        score = 0
    else:
        score = min(10, (max_repeat - 2) * 2 + max(0, len(dupes) - 3) * 1.5)

    return {
        "total_paragraphs": len(paragraphs),
        "unique_openings": len(set(openings)),
        "max_repeat_count": max_repeat,
        "repeated_openings": dupes,
        "score": round(score, 1),
        "verdict": "clean" if score < 2 else "warning" if score < 4 else "ai-like",
    }


def _check_roadmap_sentences(text: str) -> dict:
    """Detect roadmap/metacommentary sentences — an AI hallmark."""
    roadmap_patterns = [
        r"(?:this|the) (?:paper|article|study|section|chapter|report) (?:will|aims to|seeks to) ",
        r"(?:the )?(?:following|subsequent) (?:sections?|chapters?|paragraphs?) (?:will |)describ",
        r"(?:we|I) (?:will |)(?:begin by|start by|first) ",
        r"(?:we|I) (?:then|next|subsequently) ",
        r"is organized as follows",
        r"is structured as follows",
        r"the remainder of this",
        r"in the (?:next|following) section",
        r"before (?:concluding|summarizing|wrapping up)",
    ]

    sentences = _sentences(text)
    hits = []
    for s in sentences:
        s_lower = s.lower()
        for pat in roadmap_patterns:
            if re.search(pat, s_lower):
                hits.append(s[:120] + ("..." if len(s) > 120 else ""))
                break

    score = min(10, len(hits) * 3)

    return {
        "roadmap_count": len(hits),
        "examples": hits[:5],
        "score": round(score, 1),
        "verdict": "clean" if score < 2 else "warning" if score < 4 else "ai-like",
    }


# ── Main scoring ───────────────────────────────────────────────────────────

WEIGHTS = {
    "em_dashes": 1.5,
    "sentence_length": 2.0,
    "comma_density": 1.5,
    "burstiness": 2.0,
    "formulaic_phrases": 1.5,
    "paragraph_openings": 1.0,
    "roadmap_sentences": 0.5,
}


def score_text(text: str, ai_words: list[str] | None = None,
               ai_structures: list[str] | None = None,
               ai_patterns: list[str] | None = None) -> dict:
    """Run all mechanical checks and return a complete scorecard."""
    if ai_words is None:
        ai_words = DEFAULT_AI_WORDS
    if ai_structures is None:
        ai_structures = DEFAULT_AI_STRUCTURES
    if ai_patterns is None:
        ai_patterns = DEFAULT_AI_SENTENCE_PATTERNS

    sentences = _sentences(text)
    paragraphs = _paragraphs(text)

    checks = {
        "em_dashes": _check_em_dashes(text),
        "sentence_length": _check_sentence_length(sentences),
        "comma_density": _check_comma_density(sentences),
        "burstiness": _check_burstiness(sentences),
        "formulaic_phrases": _check_formulaic_phrases(
            text, ai_words, ai_structures, ai_patterns),
        "paragraph_openings": _check_paragraph_openings(paragraphs),
        "roadmap_sentences": _check_roadmap_sentences(text),
    }

    # Weighted overall score
    total_weight = sum(WEIGHTS.get(k, 1.0) for k in checks)
    weighted_sum = sum(
        checks[k]["score"] * WEIGHTS.get(k, 1.0)
        for k in checks
    )
    overall = round(weighted_sum / total_weight, 1) if total_weight > 0 else 0

    # Count flagged issues
    flags = []
    for name, check in checks.items():
        if check["verdict"] == "ai-like":
            flags.append(f"{name}: {check.get('interpretation', check['verdict'])}")

    return {
        "overall_score": overall,
        "verdict": (
            "human-like" if overall < 2.5
            else "mostly human" if overall < 4.5
            else "mixed signals" if overall < 6.5
            else "likely AI" if overall < 8.5
            else "obvious AI"
        ),
        "flags": flags,
        "checks": checks,
    }


# ── CLI ────────────────────────────────────────────────────────────────────

@click.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--json", "-j", "as_json", is_flag=True, help="Output JSON.")
@click.option("--ai-tells", "-t", type=click.Path(exists=True),
              help="JSON file with overused_words, formulaic_structures, ai_sentence_patterns.")
@click.option("--verbose", "-v", is_flag=True, help="Show flagged sentence examples.")
def main(file, as_json, ai_tells, verbose):
    """Score a paper for AI-generated text patterns using mechanical checks only."""
    text = Path(file).read_text(encoding="utf-8")

    ai_words = DEFAULT_AI_WORDS
    ai_structures = DEFAULT_AI_STRUCTURES
    ai_patterns = DEFAULT_AI_SENTENCE_PATTERNS

    if ai_tells:
        tells = json.loads(Path(ai_tells).read_text(encoding="utf-8"))
        if tells.get("overused_words"):
            ai_words = tells["overused_words"]
        if tells.get("formulaic_structures"):
            ai_structures = tells["formulaic_structures"]
        if tells.get("ai_sentence_patterns"):
            ai_patterns = tells["ai_sentence_patterns"]

    result = score_text(text, ai_words, ai_structures, ai_patterns)

    if as_json:
        click.echo(json.dumps(result, indent=2, default=str))
    else:
        _print_report(result, verbose)


def _print_report(result: dict, verbose: bool = False) -> None:
    """Pretty-print the scorecard."""
    from rich.console import Console
    from rich.table import Table

    _ = verbose  # reserved for future detailed output

    console = Console()

    verdict_color = {
        "human-like": "green",
        "mostly human": "green",
        "mixed signals": "yellow",
        "likely AI": "red",
        "obvious AI": "red",
    }

    color = verdict_color.get(result["verdict"], "white")
    console.print(f"\n[bold]AI Score:[/bold] [{color}]{result['overall_score']}/10 — {result['verdict']}[/{color}]\n")

    if result["flags"]:
        console.print("[bold yellow]Flags:[/bold yellow]")
        for f in result["flags"]:
            console.print(f"  - {f}")
        console.print("")

    table = Table(title="Detailed Checks")
    table.add_column("Check", style="cyan")
    table.add_column("Score", style="white")
    table.add_column("Verdict", style="white")
    table.add_column("Details", style="dim")

    for name, check in result["checks"].items():
        v_color = {
            "clean": "green",
            "warning": "yellow",
            "ai-like": "red",
        }.get(check["verdict"], "white")

        details = _format_details(name, check)
        table.add_row(
            name.replace("_", " ").title(),
            str(check["score"]),
            f"[{v_color}]{check['verdict']}[/{v_color}]",
            details,
        )

    console.print(table)
    console.print("")


def _format_details(name: str, check: dict) -> str:
    """Extract key detail for the summary table."""
    if name == "em_dashes":
        return f"{check['em_dash_count']} em dashes, {check['en_dash_count']} en dashes"
    elif name == "sentence_length":
        return f"avg {check['avg_words']} words, {check['over_35_words']} over 35, {check['over_50_words']} over 50"
    elif name == "comma_density":
        return f"{check['sentences_with_4plus_commas']} sentences with 4+ commas ({check['pct_of_total']}%)"
    elif name == "burstiness":
        return f"CV={check['coefficient_of_variation']}, diff={check['avg_adjacent_diff']}"
    elif name == "formulaic_phrases":
        return f"{check['total_formulaic_hits']} hits ({check['hits_per_1000_words']}/1K words)"
    elif name == "paragraph_openings":
        return f"{check['unique_openings']}/{check['total_paragraphs']} unique openings, max repeat {check['max_repeat_count']}"
    elif name == "roadmap_sentences":
        return f"{check['roadmap_count']} roadmap sentences"
    return ""


if __name__ == "__main__":
    main()
