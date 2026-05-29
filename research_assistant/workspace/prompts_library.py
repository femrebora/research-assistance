"""Prompt library — curated, copy-ready prompts for academic workflows.

Implements Section 26 of ``research_assistant_development_findings.txt``.
Each prompt is a small immutable record so the web UI can list, filter,
and inject them into Ask / Compare flows without runtime mutation.
"""
from __future__ import annotations

from dataclasses import dataclass

# ── Categories ──────────────────────────────────────────────────────────────

CATEGORIES: tuple[str, ...] = (
    "literature-review",
    "summarisation",
    "critique",
    "rewriting",
    "citation",
    "methodology",
    "thesis-defense",
    "bioinformatics",
    "grant",
    "abstract",
)


# ── Data model ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Prompt:
    """A single curated prompt."""

    slug: str
    title: str
    category: str
    purpose: str
    recommended_model: str
    body: str

    def filled(self, **variables: str) -> str:
        """Return the body with ``{placeholder}`` tokens substituted in.

        Unknown placeholders survive the call so the UI can show the user
        which fields are still empty instead of crashing.
        """
        out = self.body
        for key, value in variables.items():
            out = out.replace("{" + key + "}", value or "")
        return out


# ── Catalogue ───────────────────────────────────────────────────────────────


_PROMPTS: tuple[Prompt, ...] = (
    Prompt(
        slug="lit-review-themes",
        title="Cluster a literature corpus into themes",
        category="literature-review",
        purpose=(
            "Given a list of paper titles + abstracts, produce 4–7 coherent "
            "themes with the papers that belong to each and a short rationale."
        ),
        recommended_model="sonnet",
        body=(
            "You are helping organise a literature review on {topic}.\n"
            "Below are paper titles and abstracts. Cluster them into 4–7 "
            "themes that would form the section structure of a review chapter.\n\n"
            "For each theme provide:\n"
            "  - a short label (≤ 6 words)\n"
            "  - the IDs of the papers that belong to it\n"
            "  - 1–2 sentences explaining what unites them\n"
            "  - one open question this theme still leaves unanswered.\n\n"
            "Papers:\n{papers}\n"
        ),
    ),
    Prompt(
        slug="evidence-table",
        title="Build an evidence table from a paper",
        category="summarisation",
        purpose=(
            "Extract structured fields (population, intervention, comparator, "
            "outcomes, limitations) from a single paper for a systematic-review "
            "evidence table."
        ),
        recommended_model="sonnet",
        body=(
            "Extract a PICO + limitations evidence row from the paper below.\n"
            "Return a Markdown table with columns:\n"
            "| Field | Value |\n"
            "| ----- | ----- |\n"
            "| Population | |\n"
            "| Intervention | |\n"
            "| Comparator | |\n"
            "| Outcomes | |\n"
            "| Sample size | |\n"
            "| Methodology | |\n"
            "| Key results | |\n"
            "| Limitations | |\n"
            "| Reviewer note | |\n\n"
            "Paper:\n{paper}\n"
        ),
    ),
    Prompt(
        slug="scientific-critic",
        title="Scientific critic of a draft paragraph",
        category="critique",
        purpose=(
            "Ask a critical-reviewer persona to flag overclaims, missing "
            "citations, logical jumps, and methodology issues."
        ),
        recommended_model="claude",
        body=(
            "You are a strict but constructive scientific reviewer for a "
            "{discipline} paper. Critique the paragraph below.\n\n"
            "Highlight:\n"
            "  1. claims that are unsupported or overstated\n"
            "  2. sentences that need a citation\n"
            "  3. logical gaps between sentences\n"
            "  4. terminology that is imprecise\n"
            "  5. statistical or methodological issues if any\n\n"
            "Quote the offending span verbatim, then give a one-line fix.\n\n"
            "Paragraph:\n{paragraph}\n"
        ),
    ),
    Prompt(
        slug="academic-tone-rewrite",
        title="Rewrite in academic tone (no meaning drift)",
        category="rewriting",
        purpose=(
            "Tighten the prose into academic register without inventing new "
            "claims or removing existing ones."
        ),
        recommended_model="sonnet",
        body=(
            "Rewrite the passage below in formal academic English suitable "
            "for a {discipline} thesis.\n\n"
            "Constraints:\n"
            "  - do not introduce any new claims, numbers, or citations\n"
            "  - keep every existing citation in place\n"
            "  - prefer specific verbs over vague ones (`demonstrated`, "
            "`quantified`, `replicated`)\n"
            "  - avoid em dashes; use commas, semicolons, or full stops\n"
            "  - avoid filler (`it is worth noting that`, `interestingly`)\n\n"
            "Passage:\n{passage}\n"
        ),
    ),
    Prompt(
        slug="citation-relevance",
        title="Check a citation actually supports a claim",
        category="citation",
        purpose=(
            "Given a sentence and the cited source's abstract, judge whether "
            "the source supports the claim and to what extent."
        ),
        recommended_model="claude",
        body=(
            "Judge whether the cited source supports the claim.\n\n"
            "Claim:\n{claim}\n\n"
            "Cited source (abstract or excerpt):\n{source}\n\n"
            "Return one of: `supported`, `partially supported`, `unsupported`, "
            "`contradicted`. Then in one sentence explain why, quoting the "
            "specific phrase from the source that decided it.\n"
        ),
    ),
    Prompt(
        slug="methodology-defender",
        title="Defend a methodological choice",
        category="methodology",
        purpose=(
            "Draft the answer to `why did you choose this method?` for the "
            "thesis defense or the discussion section."
        ),
        recommended_model="claude",
        body=(
            "I need a defense paragraph for the methodological choice below.\n\n"
            "Method: {method}\n"
            "Research question: {research_question}\n"
            "Alternatives I considered: {alternatives}\n\n"
            "Write 3 short paragraphs:\n"
            "  1. why this method fits the research question best\n"
            "  2. the trade-offs vs. each alternative, with one sentence each\n"
            "  3. the threats to validity it leaves open and how I mitigate them.\n"
            "Use a confident but measured tone — no marketing language.\n"
        ),
    ),
    Prompt(
        slug="defense-jury-questions",
        title="Predict thesis defense jury questions",
        category="thesis-defense",
        purpose=(
            "Surface the questions a hostile-but-fair committee is likely to "
            "ask, grouped by theme."
        ),
        recommended_model="claude",
        body=(
            "Predict the questions a thesis committee will ask about the "
            "abstract below. Group them under: novelty, methodology, "
            "statistics, limitations, ethics, future work.\n\n"
            "For each question, add a one-line `weak-spot` note explaining "
            "what they are probing and how a candidate could be caught out.\n\n"
            "Abstract:\n{abstract}\n"
        ),
    ),
    Prompt(
        slug="ngs-variant-interpretation",
        title="ACMG-style variant interpretation draft",
        category="bioinformatics",
        purpose=(
            "Pull together a draft pathogenicity write-up from ClinVar / "
            "gnomAD / OMIM evidence notes."
        ),
        recommended_model="claude",
        body=(
            "Draft an ACMG-style interpretation for the variant below.\n\n"
            "Variant: {variant}\n"
            "Phenotype: {phenotype}\n"
            "Evidence notes (ClinVar / gnomAD / OMIM / functional / population):\n"
            "{evidence}\n\n"
            "Return:\n"
            "  - the ACMG criteria that apply, each tagged (PVS1, PS1, PM2, …)\n"
            "  - the final classification (`Pathogenic` / `Likely pathogenic` "
            "/ `VUS` / `Likely benign` / `Benign`)\n"
            "  - a 2–3 sentence rationale a clinician could paste into a report.\n"
            "Flag any criterion you applied with low confidence.\n"
        ),
    ),
    Prompt(
        slug="grant-aims",
        title="Sharpen specific aims for a grant",
        category="grant",
        purpose=(
            "Convert a loose project description into 3 tight specific-aims "
            "paragraphs with measurable outcomes."
        ),
        recommended_model="claude",
        body=(
            "Rewrite the project description below as 3 specific aims for a "
            "research grant. Each aim must have:\n"
            "  - a one-sentence headline\n"
            "  - a hypothesis or working assumption\n"
            "  - a measurable outcome with quantitative success criterion\n"
            "  - the main risk and a mitigation\n\n"
            "Project description:\n{description}\n"
        ),
    ),
    Prompt(
        slug="abstract-bilingual",
        title="Bilingual abstract (English + Turkish)",
        category="abstract",
        purpose=(
            "Produce an English abstract and a faithful Turkish translation "
            "for thesis or journal submission."
        ),
        recommended_model="sonnet",
        body=(
            "Write an academic abstract (≤ 250 words) for the paper below, "
            "then provide a faithful Turkish translation that preserves the "
            "technical terminology.\n\n"
            "Paper body:\n{body}\n\n"
            "Return:\n"
            "## Abstract (English)\n…\n\n"
            "## Özet (Türkçe)\n…\n"
        ),
    ),
)


# ── Public API ──────────────────────────────────────────────────────────────


def list_prompts(category: str | None = None) -> list[Prompt]:
    """Return prompts, optionally filtered by category slug."""
    if category in (None, "", "all"):
        return list(_PROMPTS)
    return [p for p in _PROMPTS if p.category == category]


def get_prompt(slug: str) -> Prompt | None:
    """Look up a prompt by its slug."""
    for p in _PROMPTS:
        if p.slug == slug:
            return p
    return None


def categories_with_counts() -> list[tuple[str, int]]:
    """Return `(category, count)` pairs sorted by count desc, then name."""
    tallies: dict[str, int] = {c: 0 for c in CATEGORIES}
    for p in _PROMPTS:
        tallies[p.category] = tallies.get(p.category, 0) + 1
    return sorted(tallies.items(), key=lambda item: (-item[1], item[0]))
