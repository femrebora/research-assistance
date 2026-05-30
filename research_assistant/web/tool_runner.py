"""Generic runner for the Click-based CLI modules.

Each module (ask.py, audit.py, ideas.py, …) exposes a `main` Click command.
We invoke them in-process via `click.testing.CliRunner`, which captures stdout
and returns plain text. Tools that take a `*_FILE` positional argument accept
either a path on disk OR pasted text via a textarea — pasted text is written
to a temp file before invocation, then deleted.

Adding a new tool? Add a `ToolSpec` to `TOOL_SPECS`. No other changes needed.
"""
from __future__ import annotations

import contextlib
import importlib
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from research_assistant.common import MODELS

MODEL_ALIASES: list[str] = list(MODELS.keys())


@dataclass(frozen=True)
class Field:
    """A single form field.

    `kind`:
      - "text"            single-line text input
      - "textarea"        multi-line text
      - "number"          numeric input (uses `step` and `min`/`max` if set)
      - "select"          dropdown (uses `options` or `options_key="models"`)
      - "multiselect"     checkbox group
      - "checkbox"        single boolean flag
      - "file_or_text"    textarea + optional disk path; positional file arg

    `flag`:
      - "--foo" for a Click option
      - None for a positional argument (`@click.argument`)
    """

    name: str
    label: str
    kind: str
    flag: str | None = None
    default: Any = None
    options: tuple[str, ...] = ()
    options_key: str | None = None  # e.g. "models" -> MODEL_ALIASES
    required: bool = False
    repeated: bool = False   # split value on newlines, emit flag per line (match Click multiple=True)
    help: str = ""
    placeholder: str = ""
    min: float | None = None
    max: float | None = None
    step: float | None = None
    rows: int = 8

    def resolved_options(self) -> list[str]:
        if self.options_key == "models":
            return MODEL_ALIASES
        return list(self.options)


@dataclass(frozen=True)
class ToolSpec:
    """A single CLI tool exposed in the UI."""

    name: str           # URL slug & module name
    label: str          # human-readable
    category: str       # "research" | "writing" | "audit" | "pipeline" | "meta"
    description: str
    fields: tuple[Field, ...]
    long_running: bool = False  # show extra "this may take a while" warning


# ── Tool specifications ─────────────────────────────────────────────────────


TOOL_SPECS: tuple[ToolSpec, ...] = (
    # ── Research ────────────────────────────────────────────────────────────
    ToolSpec(
        name="single_ask",
        label="Single-model ask",
        category="research",
        description="Ask any configured model a single question. No document context. Useful for quick lookups, definitions, or second opinions.",
        fields=(
            Field("prompt", "Question", "textarea", required=True, rows=4,
                  placeholder="Explain MitoScape's filtering approach.",
                  help="The question or instruction sent to the model. No document context is attached."),
            Field("model", "Model", "select", flag="--model", default="claude", options_key="models",
                  help="Which language model to ask. See README for cost / quality trade-offs per alias."),
            Field("system", "System prompt (optional)", "textarea", flag="--system", rows=3,
                  placeholder="You are a careful research assistant…",
                  help="An optional system message that steers the model's tone / role."),
            Field("temperature", "Temperature", "number", flag="--temperature", default=0.3,
                  min=0.0, max=2.0, step=0.1,
                  help="0 = deterministic, 1+ = creative. Keep low (≤0.4) for factual research."),
            Field("raw", "Raw text output", "checkbox", flag="--raw",
                  help="Skip the markdown renderer and print plain text — useful for piping."),
        ),
    ),
    ToolSpec(
        name="zot",
        label="Zotero search",
        category="research",
        description="Search your Zotero library by title/author/abstract/tag. Export as BibTeX or JSON.",
        fields=(
            Field("query", "Query", "text", required=True, placeholder="NUMT contamination",
                  help="Free-text search across titles, abstracts, tags, and authors of your Zotero library."),
            Field("limit", "Max results", "number", flag="--limit", default=15, min=1, max=200, step=1,
                  help="How many items to return at most."),
            Field("collection", "Collection (optional)", "text", flag="--collection",
                  placeholder="Chapter 1",
                  help="Restrict search to a single Zotero collection by name (partial match)."),
            Field("tag", "Tag (optional)", "text", flag="--tag",
                  help="Restrict to a single Zotero tag."),
            Field("bib", "Citekeys only", "checkbox", flag="--bib",
                  help="Output only citekeys (one per line), suitable for piping into LaTeX or .bib filters."),
            Field("export_format", "Export format", "select", flag="--export",
                  default="", options=("", "bibtex", "json"),
                  help="Export the result set as BibTeX or JSON instead of the default table."),
        ),
    ),
    ToolSpec(
        name="discover",
        label="Discover new papers",
        category="research",
        description="Find papers via OpenAlex / Semantic Scholar / Elicit. Use this to expand your library beyond what's already in Zotero.",
        fields=(
            Field("query", "Query", "text", required=True,
                  placeholder="NUMT filtering clinical mtDNA",
                  help="Keywords or phrases describing the topic — sent directly to the chosen academic API."),
            Field("source", "Source", "select", flag="--source", default="openalex",
                  options=("openalex", "semantic_scholar", "elicit"),
                  help="Which academic database to query: OpenAlex (broad), Semantic Scholar, or Elicit (AI-powered)."),
            Field("limit", "Max results", "number", flag="--limit", default=15, min=1, max=100, step=1,
                  help="Maximum number of papers to retrieve from the API."),
            Field("year_from", "Year from (optional)", "number", flag="--year-from",
                  min=1900, max=2100, step=1,
                  help="Filter out papers published before this year — useful to focus on recent literature."),
            Field("sort", "Sort by", "select", flag="--sort", default="relevance",
                  options=("relevance", "citations", "year"),
                  help="Order results by relevance score, citation count, or publication year."),
            Field("export_format", "Export format", "select", flag="--export", default="",
                  options=("", "bibtex", "json"),
                  help="Export discovered papers as BibTeX or JSON; leave blank for the default summary table."),
        ),
        long_running=True,
    ),
    ToolSpec(
        name="evidence",
        label="Evidence (PaperQA2)",
        category="research",
        description="Cited answers via PaperQA2 over your local PDFs. Slower than RAG but produces tighter source-grounded prose.",
        fields=(
            Field("question", "Question", "textarea", required=True, rows=3,
                  placeholder="What evidence exists for NUMT affecting variant calling?",
                  help="The research question PaperQA2 will answer using your local PDF collection."),
            Field("quality", "Quality preset", "select", flag="--quality", default="high_quality",
                  options=("fast", "high_quality", "wikicrow"),
                  help="PaperQA2 settings preset: 'fast' trades accuracy for speed; 'high_quality' is the default."),
            Field("model", "Model", "select", flag="--model", default="sonnet", options_key="models",
                  help="LLM used by PaperQA2 for reading and synthesising evidence from retrieved chunks."),
            Field("storage", "PDF directory (optional)", "text", flag="--storage",
                  placeholder="/home/you/Zotero/storage",
                  help="Path to the directory containing your PDFs; defaults to $ZOTERO_STORAGE if unset."),
            Field("save", "Save output as", "text", flag="--save",
                  placeholder="evidence/ch1/numt.md",
                  help="Save the cited answer to this path (relative to THESIS_ROOT). Omit to view only."),
        ),
        long_running=True,
    ),

    # ── Writing pipeline ────────────────────────────────────────────────────
    ToolSpec(
        name="ideas",
        label="Paragraph angles (ideas)",
        category="writing",
        description="Given a job statement and supporting evidence, brainstorm 3-5 distinct paragraph angles to choose from.",
        fields=(
            Field("evidence_file", "Evidence", "file_or_text", required=True, rows=10,
                  placeholder="Paste evidence notes or supply a path under THESIS_ROOT.",
                  help="Evidence notes or file path that the model will use to brainstorm paragraph angles."),
            Field("job", "Job statement", "text", flag="--job", required=True,
                  placeholder="Establish NUMT as clinically significant",
                  help="One sentence describing what this paragraph must accomplish rhetorically."),
            Field("manuscript", "Existing manuscript path (optional)", "text", flag="--manuscript",
                  help="Path to an existing manuscript paragraph for additional context; omit if starting fresh."),
            Field("model", "Model", "select", flag="--model", default="claude", options_key="models",
                  help="Which language model to use for brainstorming paragraph angles."),
            Field("temperature", "Temperature", "number", flag="--temperature",
                  default=0.4, min=0.0, max=2.0, step=0.1,
                  help="0 = deterministic, 1+ = creative. Slightly higher values (0.4-0.7) produce more varied angles."),
        ),
    ),
    ToolSpec(
        name="outline",
        label="Section outline",
        category="writing",
        description="Hierarchical outline with citation stubs. One stub per paragraph, depth-controlled, ready to draft against.",
        fields=(
            Field("evidence_file", "Evidence", "file_or_text", required=True, rows=10,
                  help="Evidence notes or file path that the outline will be structured around."),
            Field("job", "Job statement", "text", flag="--job", required=True,
                  help="One sentence describing what this section must accomplish — drives the outline's focus."),
            Field("sections", "Top-level sections", "number", flag="--sections",
                  default=3, min=1, max=10, step=1,
                  help="Number of top-level headings to generate in the outline (default 3)."),
            Field("depth", "Max nesting depth", "number", flag="--depth",
                  default=2, min=1, max=4, step=1,
                  help="How many levels of sub-points to include below each heading (default 2)."),
            Field("model", "Model", "select", flag="--model", default="claude", options_key="models",
                  help="Which language model generates the outline."),
            Field("temperature", "Temperature", "number", flag="--temperature",
                  default=0.3, min=0.0, max=2.0, step=0.1,
                  help="0 = deterministic, 1+ = creative. Keep low (≤0.4) for structured outlines."),
            Field("save", "Save outline as", "text", flag="--save",
                  placeholder="outlines/ch1.md",
                  help="Save the rendered outline to this path (relative to THESIS_ROOT). Omit to view only."),
            Field("raw", "Raw output", "checkbox", flag="--raw",
                  help="Print raw markdown instead of the rendered outline — useful for piping or saving."),
        ),
    ),
    ToolSpec(
        name="outline_recommend",
        label="Outline recommender",
        category="writing",
        description="Recommend a full paper structure from just a topic. Adds paper-type templates, organizational variants, and a map of which indexed papers cover each section.",
        fields=(
            Field("topic", "Topic / research question", "text", required=True,
                  placeholder="NUMT contamination in clinical mtDNA variant calling",
                  help="The subject of the paper. Unlike the section outline, no evidence file is needed — just the topic."),
            Field("paper_type", "Paper type", "select", flag="--paper-type",
                  default="imrad",
                  options=("imrad", "review", "systematic-review", "thesis-chapter", "methods", "case-study"),
                  help="The kind of paper to structure. Each type seeds a canonical section skeleton the model adapts."),
            Field("discipline", "Discipline (optional)", "text", flag="--discipline",
                  placeholder="bioinformatics",
                  help="Your field. Sharpens section purposes and terminology in the recommendation."),
            Field("audience", "Audience (optional)", "text", flag="--audience",
                  placeholder="domain experts",
                  help="Who will read the paper — tunes how much background each section assumes."),
            Field("target_words", "Target length (words)", "number", flag="--target-words",
                  default=6000, min=250, max=200000, step=250,
                  help="Approximate total length; drives the per-section word estimates."),
            Field("variants", "Also suggest organizational variants", "checkbox", flag="--variants",
                  help="Generate 2-3 alternative ways to organise the paper (thematic, chronological, etc.) to choose from."),
            Field("map_evidence", "Map my indexed papers to sections", "checkbox", flag="--map-evidence",
                  help="For each section, list which of your indexed Zotero papers cover it and flag coverage gaps. Needs an index."),
            Field("model", "Model", "select", flag="--model", default="claude", options_key="models",
                  help="Which language model generates the recommendation."),
            Field("temperature", "Temperature", "number", flag="--temperature",
                  default=0.3, min=0.0, max=2.0, step=0.1,
                  help="0 = deterministic, 1+ = creative. Keep low (≤0.4) for structured recommendations."),
            Field("save", "Save recommendation as", "text", flag="--save",
                  placeholder="outlines/ch1_structure.md",
                  help="Save the recommendation to this path (relative to THESIS_ROOT). Omit to view only."),
            Field("raw", "Raw output", "checkbox", flag="--raw",
                  help="Print raw markdown instead of the rendered view — useful for piping or saving."),
        ),
        long_running=True,
    ),
    ToolSpec(
        name="critique",
        label="Draft critique",
        category="writing",
        description="Single-model critique of a paragraph. Prose review or sentence-anchored (S1, S2, …) diff mode.",
        fields=(
            Field("draft_file", "Draft paragraph", "file_or_text", required=True, rows=10,
                  help="The paragraph draft to critique — paste text directly or provide a file path."),
            Field("job", "Job statement", "text", flag="--job", required=True,
                  help="One sentence describing what the paragraph must do; the critique is judged against this."),
            Field("diff_mode", "Sentence-anchored (diff) mode", "checkbox", flag="--diff",
                  help="Output sentence-by-sentence critique (S1, S2, …) instead of a prose review."),
            Field("model", "Model", "select", flag="--model", default="claude", options_key="models",
                  help="Which language model performs the critique."),
            Field("temperature", "Temperature", "number", flag="--temperature",
                  default=0.2, min=0.0, max=2.0, step=0.1,
                  help="0 = deterministic, 1+ = creative. Low values (≤0.3) give more consistent critiques."),
            Field("raw", "Raw output", "checkbox", flag="--raw",
                  help="Print raw text instead of rendered markdown panels."),
        ),
    ),
    ToolSpec(
        name="critic",
        label="Writer + critic (2-model)",
        category="writing",
        description="One model drafts the paragraph from sources, another critiques it. Useful when you want a second perspective baked into one run.",
        fields=(
            Field("job", "Job statement", "text", required=True,
                  placeholder="Define NUMT contamination clearly.",
                  help="One sentence describing what the drafted paragraph must accomplish."),
            Field("writer", "Writer model", "select", flag="--writer", default="claude",
                  options_key="models",
                  help="Model that drafts the paragraph from your source files."),
            Field("critic", "Critic model", "select", flag="--critic", default="gemini",
                  options_key="models",
                  help="Model that critiques the draft — use a different model for independent perspective."),
            Field("sources", "Source file paths (one per line)", "textarea", flag="--sources",
                  rows=4, placeholder="evidence/ch1/numt.md\nevidence/ch1/lcm.md",
                  repeated=True,
                  help="Paths to evidence files (relative to THESIS_ROOT), one per line, given to the writer."),
            Field("writer_temp", "Writer temperature", "number", flag="--writer-temp",
                  default=0.3, min=0.0, max=2.0, step=0.1,
                  help="Temperature for the writer model; slightly higher values produce more varied prose."),
            Field("critic_temp", "Critic temperature", "number", flag="--critic-temp",
                  default=0.2, min=0.0, max=2.0, step=0.1,
                  help="Temperature for the critic model; keep low (≤0.3) for consistent, focused feedback."),
            Field("save", "Save chain as", "text", flag="--save",
                  help="Save the full writer-critic chain to this path (relative to THESIS_ROOT)."),
            Field("raw", "Raw output", "checkbox", flag="--raw",
                  help="Print plain text instead of rendered panels."),
        ),
    ),
    ToolSpec(
        name="paraphrase",
        label="Paraphrase pipeline",
        category="writing",
        description="Writer → paraphraser → checker. Three models cooperate to produce a paragraph with explicit meaning verification.",
        fields=(
            Field("brief_or_draft", "Brief or existing draft", "file_or_text",
                  required=True, rows=10,
                  help="A writing brief or existing draft — the writer stage converts briefs into prose."),
            Field("writer", "Writer model (optional if Skip writer)", "select", flag="--writer",
                  default="claude", options_key="models",
                  help="Model that drafts the initial paragraph from the brief; ignored when Skip writer is on."),
            Field("paraphraser", "Paraphraser model", "select", flag="--paraphraser",
                  default="gemini", options_key="models",
                  help="Model that rewrites the draft in fresh prose to reduce source-adjacent phrasing."),
            Field("checker", "Checker model", "select", flag="--checker",
                  default="sonnet", options_key="models",
                  help="Model that verifies the paraphrase preserved the meaning of the original draft."),
            Field("sources", "Source file paths (one per line)", "textarea", flag="--sources", rows=4,
                  repeated=True,
                  help="Paths to evidence files (relative to THESIS_ROOT), one per line, for the writer stage."),
            Field("skip_writer", "Skip writer (input is already a draft)", "checkbox",
                  flag="--skip-writer",
                  help="Treat the input as an existing draft and start directly with the paraphraser."),
            Field("temperature", "Temperature", "number", flag="--temperature",
                  default=0.3, min=0.0, max=2.0, step=0.1,
                  help="Temperature for writer and paraphraser; checker is fixed at 0.1 regardless."),
            Field("save", "Save chain as", "text", flag="--save",
                  help="Save the full pipeline chain as markdown to this path (relative to THESIS_ROOT)."),
            Field("raw", "Raw output", "checkbox", flag="--raw",
                  help="Print plain text instead of rendered markdown panels."),
        ),
    ),
    ToolSpec(
        name="coherence",
        label="Chapter coherence",
        category="writing",
        description="Whole-chapter analysis: transitions, redundancy, thesis support. Run on multi-paragraph drafts.",
        fields=(
            Field("draft_file", "Chapter draft", "file_or_text", required=True, rows=14,
                  help="Multi-paragraph chapter draft to analyse for transitions, redundancy, and thesis support."),
            Field("thesis", "Thesis sentence", "text", flag="--thesis", required=True,
                  placeholder="NUMT filtering is mandatory for clinical mtDNA pipelines.",
                  help="One sentence stating the chapter's central argument; each paragraph is judged against it."),
            Field("model", "Model", "select", flag="--model", default="claude", options_key="models",
                  help="Which language model performs the coherence analysis."),
            Field("temperature", "Temperature", "number", flag="--temperature",
                  default=0.2, min=0.0, max=2.0, step=0.1,
                  help="0 = deterministic, 1+ = creative. Keep very low (≤0.3) for consistent analysis."),
            Field("max_chars_per_paragraph", "Max chars/paragraph in prompt", "number",
                  flag="--max-chars-per-paragraph", default=600, min=100, max=4000, step=50,
                  help="Truncate each paragraph in the prompt to this many characters to stay within token limits."),
            Field("raw", "Raw output", "checkbox", flag="--raw",
                  help="Print raw text instead of rendered markdown."),
        ),
    ),

    # ── Audit & verify ──────────────────────────────────────────────────────
    ToolSpec(
        name="paraphrase_check",
        label="Paraphrase similarity check",
        category="audit",
        description="Flag paragraphs in your draft that drifted too close to source wording. Catches accidental near-quotes.",
        fields=(
            Field("draft_file", "Chapter draft", "file_or_text", required=True, rows=14,
                  help="Chapter draft whose paragraphs will be compared against RAG index chunks for similarity."),
            Field("threshold", "Similarity threshold", "number", flag="--threshold",
                  default=0.85, min=0.5, max=1.0, step=0.01,
                  help="Cosine similarity threshold (0-1); paragraphs above this score are flagged. Higher = stricter."),
            Field("top", "Top-N matches per paragraph", "number", flag="--top",
                  default=2, min=1, max=10, step=1,
                  help="How many nearest source chunks to compare against each paragraph."),
            Field("min_chars", "Skip paragraphs shorter than", "number", flag="--min-chars",
                  default=40, min=10, max=500, step=10,
                  help="Ignore paragraphs shorter than this many characters (avoids flagging headings or captions)."),
            Field("embedding_model", "Embedding model", "text", flag="--embedding-model",
                  help="Embedding model to use; must match the model used to build the RAG index."),
            Field("as_json", "JSON output", "checkbox", flag="--json",
                  help="Output results as JSON instead of a human-readable table."),
            Field("show_source", "Show matched source excerpts", "checkbox", flag="--show-source",
                  help="Print the matched source text excerpt next to each flagged paragraph."),
        ),
    ),
    ToolSpec(
        name="audit",
        label="Citation audit",
        category="audit",
        description="Per-source counts, over-cited papers, unused bib entries, citation density.",
        fields=(
            Field("draft_file", "Chapter draft", "file_or_text", required=True, rows=14,
                  help="Chapter draft to audit for citation counts, over-cited papers, and unused .bib entries."),
            Field("bib", "Path to .bib file", "text", flag="--bib", default="bib/thesis.bib",
                  help="Path to the .bib file (relative to THESIS_ROOT) used to identify unused entries."),
            Field("over_cite", "Flag sources cited more than", "number", flag="--over-cite",
                  default=6, min=2, max=50, step=1,
                  help="Flag any source cited more than this many times as potentially over-cited."),
            Field("as_json", "JSON output", "checkbox", flag="--json",
                  help="Output citation audit results as JSON instead of tables."),
        ),
    ),
    ToolSpec(
        name="verify",
        label="Citation verification",
        category="audit",
        description="Check every [@citekey] in your draft resolves to an entry in your BibTeX file. Catches typos and hallucinated keys.",
        fields=(
            Field("draft_file", "Draft", "file_or_text", required=True, rows=14,
                  help="Chapter draft whose [@citekey] references will be checked against the .bib file."),
            Field("bib", "Path to .bib file", "text", flag="--bib", default="bib/thesis.bib",
                  help="Path to the .bib file (relative to THESIS_ROOT) to validate citekeys against."),
        ),
    ),
    ToolSpec(
        name="claim_verify",
        label="Semantic claim audit",
        category="audit",
        description="For each sentence/claim in your draft, retrieve from your RAG index and judge SUPPORTED / PARTIAL / UNSUPPORTED / CONTRADICTED.",
        fields=(
            Field("draft_file", "Draft", "file_or_text", required=True, rows=14,
                  help="Chapter draft whose sentences will each be adjudicated against your RAG index."),
            Field("model", "Adjudicator model", "select", flag="--model", default="sonnet",
                  options_key="models",
                  help="LLM that reads retrieved chunks and judges each claim as SUPPORTED / PARTIAL / UNSUPPORTED / CONTRADICTED."),
            Field("k", "Chunks per claim", "number", flag="--k", default=6, min=1, max=30, step=1,
                  help="Number of RAG chunks to retrieve per claim for adjudication context."),
            Field("threshold", "Similarity threshold", "number", flag="--threshold",
                  default=0.30, min=0.0, max=1.0, step=0.05,
                  help="Cosine similarity threshold for retrieval; lower values cast a wider net."),
            Field("min_chars", "Skip claims shorter than", "number", flag="--min-chars",
                  default=40, min=10, max=500, step=10,
                  help="Skip sentences shorter than this many characters (filters out headings and captions)."),
            Field("limit", "Max claims (optional)", "number", flag="--limit", min=1, max=500, step=1,
                  help="Audit at most this many claims; leave blank to process all sentences in the draft."),
            Field("as_json", "JSON output", "checkbox", flag="--json",
                  help="Output claim-by-claim verdicts as JSON instead of a table."),
        ),
        long_running=True,
    ),

    ToolSpec(
        name="originality",
        label="Originality check",
        category="audit",
        description=(
            "Flag paragraphs that look too similar to (a) your own indexed library "
            "or (b) published abstracts on OpenAlex / Crossref. Not a true plagiarism "
            "detector -- it produces leads for human review."
        ),
        fields=(
            Field("draft_file", "Draft", "file_or_text", required=True, rows=14,
                  help="Paste the chapter / section text, or supply a path under THESIS_ROOT."),
            Field("sources", "Sources to check", "text", flag="--sources",
                  default="internal,openalex,crossref",
                  help=("Comma-separated subset of internal, openalex, crossref. "
                        "Internal checks your indexed Zotero papers; the other two query "
                        "published academic abstracts.")),
            Field("internal_threshold", "Internal similarity threshold", "number",
                  flag="--internal-threshold", default=0.85, min=0.5, max=1.0, step=0.01,
                  help="Higher = stricter. 0.85 catches near-verbatim; 0.75 catches close paraphrase."),
            Field("external_threshold", "External similarity threshold", "number",
                  flag="--external-threshold", default=0.80, min=0.5, max=1.0, step=0.01,
                  help="Cosine similarity between your paragraph and the matched abstract."),
            Field("min_chars", "Skip paragraphs shorter than", "number", flag="--min-chars",
                  default=150, min=10, max=500, step=10,
                  help="Tiny paragraphs are too noisy to check reliably."),
            Field("as_json", "JSON output", "checkbox", flag="--json",
                  help="Output as JSON instead of the rendered table."),
        ),
        long_running=True,
    ),

    # ── Pipeline & meta ─────────────────────────────────────────────────────
    ToolSpec(
        name="pipeline",
        label="Full pipeline",
        category="pipeline",
        description="Retrieve → draft → paraphrase → critique → verify → log. End-to-end paragraph production from a single question.",
        fields=(
            Field("question", "Question", "textarea", required=True, rows=3,
                  placeholder="What approaches exist for NUMT filtering in clinical mtDNA?",
                  help="The research question that drives the full pipeline: retrieve → draft → paraphrase → critique → verify."),
            Field("writer", "Writer model", "select", flag="--writer",
                  default="claude", options_key="models",
                  help="Model that drafts the initial paragraph from retrieved RAG chunks."),
            Field("paraphraser", "Paraphraser model", "select", flag="--paraphraser",
                  default="gemini", options_key="models",
                  help="Model that rewrites the draft in fresh prose to reduce source-adjacent phrasing."),
            Field("critic", "Critic model", "select", flag="--critic",
                  default="sonnet", options_key="models",
                  help="Model that critiques the paraphrased paragraph for clarity and accuracy."),
            Field("k", "RAG chunks to retrieve", "number", flag="--k",
                  default=12, min=1, max=50, step=1,
                  help="Number of RAG chunks to retrieve from your index to ground the writer's draft."),
            Field("threshold", "Similarity threshold", "number", flag="--threshold",
                  default=0.30, min=0.0, max=1.0, step=0.05,
                  help="Cosine similarity threshold for RAG retrieval; lower values surface more (possibly noisier) chunks."),
            Field("temperature", "Temperature", "number", flag="--temperature",
                  default=0.3, min=0.0, max=2.0, step=0.1,
                  help="Temperature for the writer and paraphraser; keep low (≤0.4) for factual research writing."),
            Field("bib", "Bibliography", "text", flag="--bib", default="bib/thesis.bib",
                  help="Path to .bib file used by the citation verifier step (relative to THESIS_ROOT)."),
            Field("no_verify", "Skip citation verifier", "checkbox", flag="--no-verify",
                  help="Omit the citation verification step — useful for speed when citekeys are already trusted."),
            Field("save", "Save report as", "text", flag="--save",
                  help="Save the full pipeline report to this path (relative to THESIS_ROOT)."),
            Field("raw", "Raw output", "checkbox", flag="--raw",
                  help="Print plain text instead of rendered panels — useful for piping or scripting."),
        ),
        long_running=True,
    ),
    ToolSpec(
        name="disclose",
        label="AI-usage disclosure",
        category="meta",
        description="Generate venue-ready AI-usage disclosure from your call logs (~/thesis/logs/ by default).",
        fields=(
            Field("since", "Since (YYYY-MM-DD, optional)", "text", flag="--since",
                  help="Include only AI call logs on or after this date; leave blank to include all logs."),
            Field("until", "Until (YYYY-MM-DD, optional)", "text", flag="--until",
                  help="Include only AI call logs on or before this date; leave blank to include all logs."),
            Field("venue", "Venue style", "select", flag="--venue", default="generic",
                  options=("generic", "elsevier", "springer", "wiley", "nature", "ieee", "acm"),
                  help="Disclosure template style — choose the journal or publisher you're submitting to."),
            Field("as_json", "JSON output", "checkbox", flag="--json",
                  help="Output the disclosure data as machine-readable JSON instead of rendered prose."),
            Field("save", "Save disclosure as", "text", flag="--save",
                  help="Save the rendered disclosure statement to this path (relative to THESIS_ROOT)."),
            Field("log_dir", "Log directory override", "text", flag="--log-dir",
                  help="Override the default log directory (~/thesis/logs) to read AI usage logs from."),
        ),
    ),
)


def get_spec(name: str) -> ToolSpec | None:
    for spec in TOOL_SPECS:
        if spec.name == name:
            return spec
    return None


def specs_by_category() -> dict[str, list[ToolSpec]]:
    """Group tools by category, preserving definition order within each."""
    grouped: dict[str, list[ToolSpec]] = {}
    for spec in TOOL_SPECS:
        grouped.setdefault(spec.category, []).append(spec)
    return grouped


# ── Module name → Python import path ────────────────────────────────────────


_MODULE_BY_NAME: Mapping[str, str] = {
    # research subpackage
    "single_ask": "research_assistant.research.ask",
    "zot":        "research_assistant.research.zot",
    "discover":   "research_assistant.research.discover",
    "evidence":   "research_assistant.research.evidence",
    # writing subpackage
    "ideas":      "research_assistant.writing.ideas",
    "outline":    "research_assistant.writing.outline",
    "outline_recommend": "research_assistant.writing.outline_recommender",
    "critique":   "research_assistant.writing.critique",
    "critic":     "research_assistant.writing.critic",
    "paraphrase": "research_assistant.writing.paraphrase",
    "coherence":  "research_assistant.writing.coherence",
    "disclose":   "research_assistant.writing.disclose",
    # verification subpackage
    "paraphrase_check": "research_assistant.verification.paraphrase_check",
    "audit":            "research_assistant.verification.audit",
    "verify":           "research_assistant.verification.verify",
    "claim_verify":     "research_assistant.verification.claim_verify",
    "originality":      "research_assistant.verification.originality",
    # top-level
    "pipeline":   "research_assistant.pipeline",
}


def _argv_for(spec: ToolSpec, form: Mapping[str, Any], scratch_files: list[Path]) -> list[str]:
    """Convert a form-data dict into the argv list expected by the Click command.

    `scratch_files` accumulates temp files we created so the caller can clean up.
    """
    argv: list[str] = []

    # First, collect positional arguments (flag is None) in declaration order
    positionals: list[tuple[Field, Any]] = []
    options: list[tuple[Field, Any]] = []
    for fld in spec.fields:
        raw = form.get(fld.name)
        if fld.flag is None:
            positionals.append((fld, raw))
        else:
            options.append((fld, raw))

    for fld, raw in positionals:
        value = _materialize_arg_value(fld, raw, scratch_files)
        if value is None:
            if fld.required:
                raise ValueError(f"Field '{fld.label}' is required.")
            continue
        argv.append(str(value))

    for fld, raw in options:
        if fld.kind == "checkbox":
            if _truthy(raw):
                argv.append(fld.flag)  # type: ignore[arg-type]
            continue
        value = _materialize_arg_value(fld, raw, scratch_files)
        if value is None or value == "":
            continue
        if fld.repeated:
            for line in str(value).splitlines():
                line = line.strip()
                if line:
                    argv.extend([fld.flag, line])
            continue
        argv.extend([fld.flag, str(value)])  # type: ignore[list-item]

    return argv


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() in {"on", "true", "1", "yes"}


def _materialize_arg_value(fld: Field, raw: Any, scratch_files: list[Path]) -> str | None:
    """Convert form value to the string Click expects; write text→temp file when needed."""
    if fld.kind == "file_or_text":
        # form may contain both `name_text` (textarea) and `name_path` (path on disk).
        # If the path is supplied, use it; otherwise spool the textarea into a temp file.
        # The actual form keys come from the template (see tools.html).
        text = (raw or "").strip() if isinstance(raw, str) else ""
        path = ""
        # See collect_form for how these get combined.
        if isinstance(raw, dict):
            text = (raw.get("text") or "").strip()
            path = (raw.get("path") or "").strip()
        if path:
            return path
        if not text:
            return None
        suffix = ".md"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, prefix=f"ra_{fld.name}_", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(text)
            tmp_name = tmp.name
        scratch_files.append(Path(tmp_name))
        return tmp_name

    if raw is None or raw == "":
        return None
    if fld.kind == "number":
        # Pass through as string; Click will coerce.
        return str(raw)
    return str(raw)


def collect_form(spec: ToolSpec, form: Mapping[str, str]) -> dict[str, Any]:
    """Group raw form keys into a per-field dict.

    For `file_or_text` fields we expect two keys: `<name>_text` and `<name>_path`.
    Other fields use the field name directly.
    """
    collected: dict[str, Any] = {}
    for fld in spec.fields:
        if fld.kind == "file_or_text":
            collected[fld.name] = {
                "text": form.get(f"{fld.name}_text", ""),
                "path": form.get(f"{fld.name}_path", ""),
            }
        elif fld.kind == "checkbox":
            collected[fld.name] = form.get(fld.name) in {"on", "true", "1", "yes"}
        else:
            collected[fld.name] = form.get(fld.name, "")
    return collected


@dataclass
class ToolResult:
    output: str
    exit_code: int
    argv: list[str]
    error: str | None = None


def run_tool(name: str, form_data: Mapping[str, str]) -> ToolResult:
    """Invoke the tool's Click command with form-derived argv. Returns captured stdout."""
    spec = get_spec(name)
    if spec is None:
        return ToolResult(output="", exit_code=2, argv=[], error=f"Unknown tool '{name}'.")

    module_name = _MODULE_BY_NAME.get(name)
    if module_name is None:
        return ToolResult(output="", exit_code=2, argv=[], error=f"No module mapping for tool '{name}'.")

    collected = collect_form(spec, form_data)
    scratch: list[Path] = []
    try:
        argv = _argv_for(spec, collected, scratch)
    except ValueError as exc:
        return ToolResult(output="", exit_code=2, argv=[], error=str(exc))

    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        return ToolResult(output="", exit_code=1, argv=argv, error=f"Import failed: {exc}")

    cmd = getattr(module, "main", None)
    if cmd is None:
        return ToolResult(output="", exit_code=1, argv=argv, error=f"Module '{module_name}' has no `main` Click command.")

    runner = CliRunner(mix_stderr=False)
    # Force monochrome / no-TTY output for rich-based modules.
    env = {"FORCE_COLOR": "0", "NO_COLOR": "1", "TERM": "dumb"}
    try:
        result = runner.invoke(cmd, argv, catch_exceptions=True, env=env)
    finally:
        for path in scratch:
            with contextlib.suppress(OSError):
                os.unlink(path)

    output = result.output or ""
    err = None
    if result.exit_code != 0:
        # SystemExit on its own is just Click's normal exit channel — only treat
        # it as an error if there's no usable stdout to show the user.
        exc = result.exception
        if exc is not None and not isinstance(exc, SystemExit):
            err = f"{type(exc).__name__}: {exc}"
        elif result.stderr_bytes:
            stderr = result.stderr_bytes.decode("utf-8", errors="replace").strip()
            if stderr:
                err = stderr
        elif not output.strip():
            err = f"Tool exited with code {result.exit_code} and produced no output."

    return ToolResult(output=output, exit_code=result.exit_code, argv=argv, error=err)
