#!/usr/bin/env python3
"""outline_recommender.py — turn a *topic* into a recommended paper structure.

Where ``outline.py`` needs you to already know your one-sentence job statement
and to supply a gathered evidence file, this tool starts one step earlier: give
it a topic / research question and a paper type, and it recommends a full
section-by-section skeleton — purpose per section, suggested length, note-style
paragraph stubs, optional organizational variants, and (when a Zotero index
exists) a map of which indexed papers cover each section plus coverage gaps.

It is additive: ``outline.py`` is unchanged. Use the recommender to decide the
shape of a paper, then ``outline.py`` to flesh out a single section.

Usage:
    ./outline_recommender.py "NUMT contamination in clinical mtDNA" \\
        --paper-type imrad --discipline bioinformatics --target-words 6000

    ./outline_recommender.py "CRISPR delivery methods" \\
        --paper-type review --variants

    ./outline_recommender.py "Tool X for variant calling" \\
        --paper-type methods --map-evidence --save outlines/toolx.md
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

import click
from rich.console import Console
from rich.markdown import Markdown

from research_assistant.common import MODELS, ask_model, save_file

console = Console()

MIN_TARGET_WORDS = 250
MAX_TARGET_WORDS = 200_000
DEFAULT_TARGET_WORDS = 6000


# ── Paper-type templates ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class SectionTemplate:
    """One canonical section: a name, what it achieves, and its share of the
    total word budget (shares within a paper type sum to ~1.0)."""

    name: str
    purpose: str
    share: float


@dataclass(frozen=True)
class PaperType:
    """An ordered list of canonical sections for one kind of paper."""

    key: str
    label: str
    sections: tuple[SectionTemplate, ...]


PAPER_TYPES: dict[str, PaperType] = {
    "imrad": PaperType(
        "imrad", "IMRaD research article",
        (
            SectionTemplate("Introduction", "Motivate the problem and state the gap and aim.", 0.18),
            SectionTemplate("Methods", "Describe data, materials, and analysis so others can reproduce.", 0.22),
            SectionTemplate("Results", "Report findings objectively, no interpretation.", 0.25),
            SectionTemplate("Discussion", "Interpret results against the literature; state limitations.", 0.25),
            SectionTemplate("Conclusion", "Summarise contribution and future work.", 0.10),
        ),
    ),
    "review": PaperType(
        "review", "Narrative / literature review",
        (
            SectionTemplate("Introduction", "Define scope, motivate the review, state the guiding question.", 0.15),
            SectionTemplate("Background", "Establish the shared concepts and terminology.", 0.20),
            SectionTemplate("Thematic synthesis", "Organise and compare the literature by theme.", 0.40),
            SectionTemplate("Open challenges", "Identify gaps, contradictions, and unresolved debates.", 0.15),
            SectionTemplate("Conclusion", "Synthesise the state of the field and future directions.", 0.10),
        ),
    ),
    "systematic-review": PaperType(
        "systematic-review", "PRISMA-style systematic review",
        (
            SectionTemplate("Introduction", "State the review question (PICO) and rationale.", 0.12),
            SectionTemplate("Methods", "Eligibility, search strategy, screening, and risk-of-bias plan.", 0.23),
            SectionTemplate("Results", "PRISMA flow, study characteristics, and synthesised findings.", 0.30),
            SectionTemplate("Discussion", "Strength of evidence, limitations, and applicability.", 0.23),
            SectionTemplate("Conclusion", "Implications for practice and research.", 0.12),
        ),
    ),
    "thesis-chapter": PaperType(
        "thesis-chapter", "Thesis chapter",
        (
            SectionTemplate("Chapter introduction", "Position the chapter within the thesis and state its objective.", 0.15),
            SectionTemplate("Background and theory", "Establish the conceptual frame this chapter builds on.", 0.25),
            SectionTemplate("Core argument / work", "Develop the chapter's central contribution.", 0.40),
            SectionTemplate("Discussion", "Relate findings to the thesis question and prior chapters.", 0.12),
            SectionTemplate("Chapter summary", "Recap and bridge to the next chapter.", 0.08),
        ),
    ),
    "methods": PaperType(
        "methods", "Methods / tools paper",
        (
            SectionTemplate("Introduction", "Motivate the need for the new method or tool.", 0.18),
            SectionTemplate("Design and implementation", "Describe the method, architecture, and design choices.", 0.30),
            SectionTemplate("Validation", "Benchmark against alternatives; report accuracy and cost.", 0.27),
            SectionTemplate("Usage / availability", "Installation, usage, and reproducibility details.", 0.13),
            SectionTemplate("Conclusion", "Summarise advantages and limitations.", 0.12),
        ),
    ),
    "case-study": PaperType(
        "case-study", "Case study / report",
        (
            SectionTemplate("Introduction", "Introduce the case and why it matters.", 0.18),
            SectionTemplate("Case description", "Present the case context, timeline, and observations.", 0.32),
            SectionTemplate("Analysis", "Interpret the case against relevant theory or literature.", 0.30),
            SectionTemplate("Lessons / implications", "Draw transferable lessons.", 0.12),
            SectionTemplate("Conclusion", "Close with takeaways.", 0.08),
        ),
    ),
}


# ── Pure helpers ─────────────────────────────────────────────────────────────


def estimate_words(total: int, share: float) -> int:
    """Words for a section, rounded to the nearest 50 for a clean estimate."""
    return int(round(total * share / 50.0)) * 50


def _require_type(paper_type_key: str) -> PaperType:
    ptype = PAPER_TYPES.get(paper_type_key)
    if ptype is None:
        raise ValueError(
            f"Unknown paper type '{paper_type_key}'. "
            f"Choose one of: {', '.join(PAPER_TYPES)}"
        )
    return ptype


def _section_lines(ptype: PaperType, target_words: int) -> str:
    lines = []
    for s in ptype.sections:
        words = estimate_words(target_words, s.share)
        lines.append(f"- {s.name} (~{words} words): {s.purpose}")
    return "\n".join(lines)


def build_structure_prompt(
    *,
    topic: str,
    paper_type_key: str,
    discipline: str,
    audience: str,
    target_words: int,
) -> str:
    """Prompt for the main structure pass. Raises ValueError on bad type."""
    ptype = _require_type(paper_type_key)
    discipline_line = f"Discipline / field: {discipline}\n" if discipline.strip() else ""
    audience_line = f"Target audience: {audience}\n" if audience.strip() else ""
    return f"""You are helping me plan a {ptype.label} before I write any prose.
I will write all the prose myself. Your job is to recommend a tight, fillable
structure I can draft against.

## Topic / research question
{topic}

{discipline_line}{audience_line}Target length: about {target_words} words total.

## Canonical {ptype.label} sections (adapt these to my topic)
{_section_lines(ptype, target_words)}

## Your task

Produce a recommended outline with these constraints:

1. Start from the canonical sections above but ADAPT their names and order to my
   specific topic. Add or merge sections where the topic clearly calls for it.
2. For each section give: a one-line **purpose**, an estimated **word count**,
   and 2-4 **paragraph stubs**.
3. Each paragraph stub is note-taking style — one phrase describing the topic
   only, NOT polished prose. "Define NUMT and clinical impact" is right;
   "NUMTs are nuclear copies of mitochondrial DNA that..." is wrong.
4. Where a section will require sources I likely have not gathered yet, append
   [needs evidence] to that stub.
5. End with a short "## How to use this" note: which section to draft first and
   why.

Format the result as markdown with one `##` heading per section.
"""


def build_variants_prompt(*, topic: str, paper_type_key: str, discipline: str) -> str:
    """Prompt for 2-3 alternative organizational schemes."""
    ptype = _require_type(paper_type_key)
    discipline_line = f"Discipline / field: {discipline}\n" if discipline.strip() else ""
    return f"""I am planning a {ptype.label} on the topic below and want to compare
different ways to ORGANISE it before committing.

## Topic / research question
{topic}

{discipline_line}
## Your task

Propose exactly 3 alternative organizational schemes for this paper — for
example thematic, chronological, methodological, by-stakeholder, or
problem-then-solution. For each scheme:

1. Give it a short name and a one-line rationale (when this organisation works
   best).
2. List its top-level sections (names only, in order).

Keep it compact — this is a menu to choose from, not a full outline. Format as
markdown with one `##` heading per scheme.
"""


def build_evidence_map(
    topic: str,
    paper_type_key: str,
    *,
    retriever,
    k: int = 6,
) -> dict[str, list[str]]:
    """For each canonical section, query the index and collect supporting
    citekeys (deduped, order-preserved). Sections with no matches map to an
    empty list — i.e. a coverage gap. ``retriever`` is injected for testability;
    it is called as ``retriever(query, k=...)`` and returns chunk dicts with
    ``metadata.citekey``.
    """
    ptype = _require_type(paper_type_key)
    emap: dict[str, list[str]] = {}
    for s in ptype.sections:
        query = f"{topic} — {s.name}: {s.purpose}"
        try:
            chunks = retriever(query, k=k)
        except TypeError:
            chunks = retriever(query)
        seen: list[str] = []
        for ch in chunks or []:
            ck = (ch.get("metadata") or {}).get("citekey", "")
            if ck and ck not in seen:
                seen.append(ck)
        emap[s.name] = seen
    return emap


def render_evidence_coverage(evidence_map: dict[str, list[str]]) -> str:
    """Render the evidence map as a markdown coverage block."""
    lines = ["## Evidence coverage (from your indexed library)", ""]
    for section, citekeys in evidence_map.items():
        if citekeys:
            stubs = "; ".join(f"@{c}" for c in citekeys)
            lines.append(f"- **{section}** — {stubs}")
        else:
            lines.append(f"- **{section}** — _gap: no indexed sources matched_")
    lines.append("")
    return "\n".join(lines)


def _default_retriever():
    """Lazily build a retriever backed by the Zotero RAG index. Returns None if
    no index is available (so the recommender degrades gracefully)."""
    try:
        from research_assistant.researcher import _get_collection, retrieve_chunks
    except Exception:
        return None
    try:
        collection = _get_collection()
    except Exception:
        return None

    def _retr(query: str, k: int = 6):
        return retrieve_chunks(query, collection=collection, k=k)

    return _retr


# ── CLI ──────────────────────────────────────────────────────────────────────


@click.command()
@click.argument("topic")
@click.option("--paper-type", "-p", default="imrad",
              type=click.Choice(list(PAPER_TYPES.keys())),
              help="Kind of paper to structure (imrad, review, systematic-review, "
                   "thesis-chapter, methods, case-study).")
@click.option("--discipline", "-d", default="",
              help="Field / discipline, e.g. bioinformatics. Sharpens the recommendation.")
@click.option("--audience", "-a", default="",
              help="Who will read it, e.g. 'domain experts' or 'a general science audience'.")
@click.option("--target-words", "-w", default=DEFAULT_TARGET_WORDS, type=int,
              help=f"Approximate total length; drives per-section word estimates "
                   f"({MIN_TARGET_WORDS}-{MAX_TARGET_WORDS}).")
@click.option("--variants", is_flag=True,
              help="Also generate 2-3 alternative organizational schemes to choose from.")
@click.option("--map-evidence", is_flag=True,
              help="Map your indexed Zotero papers onto each section and flag coverage gaps.")
@click.option("--model", "-m", default="claude",
              type=click.Choice(list(MODELS.keys())),
              help="Which model generates the recommendation.")
@click.option("--temperature", "-t", default=0.3, type=float,
              help="Model temperature (0.0-2.0). Keep low for structured output.")
@click.option("--save", "-o", default=None,
              help="Save the recommendation to this path (relative to THESIS_ROOT).")
@click.option("--raw", is_flag=True,
              help="Print raw markdown instead of the rendered view.")
def main(topic, paper_type, discipline, audience, target_words, variants,
         map_evidence, model, temperature, save, raw):
    """Recommend a paper structure from a TOPIC."""
    if not topic.strip():
        click.echo("Error: topic must not be empty.", err=True)
        sys.exit(1)
    if target_words < MIN_TARGET_WORDS or target_words > MAX_TARGET_WORDS:
        click.echo(
            f"Error: --target-words must be {MIN_TARGET_WORDS}-{MAX_TARGET_WORDS}.",
            err=True,
        )
        sys.exit(1)

    console.print(
        f"[dim]→ {model} | {PAPER_TYPES[paper_type].label} | "
        f"~{target_words} words | topic: {topic}[/dim]\n"
    )

    structure_prompt = build_structure_prompt(
        topic=topic,
        paper_type_key=paper_type,
        discipline=discipline,
        audience=audience,
        target_words=target_words,
    )
    result = ask_model(structure_prompt, model=model, temperature=temperature,
                       max_tokens=6000)
    parts = [result["text"]]

    total_cost = result.get("cost") or 0.0
    in_tok = result.get("input_tokens") or 0
    out_tok = result.get("output_tokens") or 0

    if variants:
        variants_prompt = build_variants_prompt(
            topic=topic, paper_type_key=paper_type, discipline=discipline,
        )
        vresult = ask_model(variants_prompt, model=model, temperature=temperature,
                            max_tokens=3000)
        parts.append("\n\n---\n\n## Organizational variants\n\n" + vresult["text"])
        total_cost += vresult.get("cost") or 0.0
        in_tok += vresult.get("input_tokens") or 0
        out_tok += vresult.get("output_tokens") or 0

    if map_evidence:
        retriever = _default_retriever()
        if retriever is None:
            parts.append(
                "\n\n---\n\n> Evidence mapping skipped: no Zotero index found. "
                "Index your library, then re-run with --map-evidence."
            )
        else:
            emap = build_evidence_map(topic, paper_type, retriever=retriever)
            parts.append("\n\n---\n\n" + render_evidence_coverage(emap))

    output = "\n".join(parts)

    if save:
        header = (
            f"# Recommended outline\n\n"
            f"**Topic:** {topic}\n"
            f"**Paper type:** {PAPER_TYPES[paper_type].label}\n"
            f"**Model:** {model} ({MODELS[model]})\n\n---\n\n"
        )
        path = save_file(save, header + output)
        console.print(f"[green]Recommendation saved: {path}[/green]\n")

    if raw:
        click.echo(output)
    else:
        console.print(Markdown(output))

    if in_tok or out_tok:
        console.print(
            f"\n[dim]tokens: {in_tok} in, {out_tok} out"
            + (f" | cost: ~${total_cost:.4f}" if total_cost else "")
            + "[/dim]"
        )


if __name__ == "__main__":
    main()
