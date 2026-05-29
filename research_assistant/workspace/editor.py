"""AI editor — apply a natural-language instruction to the project document.

The contract is intentionally narrow so the UI stays simple:

* Inputs: current document, a free-text instruction, an optional list of
  local PDF excerpts to use as evidence, a model alias.
* Output: the full revised document (so we can replace in one shot) plus
  a short ``summary`` of what changed and the list of source excerpts that
  were attached.

The system prompt is strict: do not invent citations, do not delete
existing references unless explicitly asked, preserve Markdown headings.
This keeps the rewrite predictable.
"""
from __future__ import annotations

from dataclasses import dataclass

from research_assistant.common import MODELS, ask_model
from research_assistant.workspace import library
from research_assistant.workspace.projects import Project, project_context_block

# ── System prompt ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are an academic writing assistant editing a single Markdown document. "
    "Follow these rules strictly:\n"
    "  1. Return the FULL updated document — never a diff, snippet, or excerpt.\n"
    "  2. Preserve every existing Markdown heading unless the instruction "
    "asks to remove or rename one.\n"
    "  3. Do not invent citations, author names, or DOIs. If a citation is "
    "needed but unknown, write `[citation needed]` inline.\n"
    "  4. Do not remove existing citations unless the instruction explicitly "
    "asks for it.\n"
    "  5. Match the existing academic register; avoid em dashes, marketing "
    "language, and filler.\n"
    "  6. If asked to add a paragraph in a particular section, place it at "
    "the end of that section.\n"
    "  7. End your output with a single line beginning with `SUMMARY:` "
    "containing a one-sentence note on what changed. Place this line on its "
    "own at the very end after the document, separated by a blank line."
)


@dataclass(frozen=True)
class EditOutcome:
    """Result of a single AI edit."""

    new_document: str
    summary: str
    model: str
    sources_used: tuple[str, ...]
    input_tokens: int
    output_tokens: int
    cost: float
    error: str | None = None


# ── Public API ──────────────────────────────────────────────────────────────


def apply_edit(
    *,
    current_document: str,
    instruction: str,
    sources: tuple[str, ...] = (),
    model: str = "sonnet",
    project: Project | None = None,
    temperature: float = 0.3,
    max_tokens: int = 8000,
) -> EditOutcome:
    """Run one edit pass and return the new document + metadata.

    Parameters
    ----------
    current_document
        The Markdown text currently on disk.
    instruction
        Plain-English instruction from the user, e.g. ``"add a paragraph
        to Methods on sample size justification"``.
    sources
        Relative paths of PDFs inside :data:`library.DOCS_DIR` to attach as
        excerpts. Each excerpt is bounded by ``library.MAX_EXCERPT_CHARS``.
    model
        Model alias from :mod:`research_assistant.common`.
    project
        Optional project context — its title / question / citation style
        is appended as a preamble.
    """
    if not instruction.strip():
        return _empty_outcome(model, "Instruction is empty.")
    if model not in MODELS:
        return _empty_outcome(
            model,
            f"Unknown model '{model}'. Available: {', '.join(sorted(MODELS))}",
        )

    excerpts = _build_excerpt_block(sources)
    context = project_context_block(project) if project else ""

    prompt = _build_prompt(
        context=context,
        current_document=current_document,
        instruction=instruction,
        excerpts=excerpts,
    )

    try:
        result = ask_model(
            prompt,
            model=model,
            system=_SYSTEM_PROMPT,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        return _empty_outcome(model, str(exc))

    text = result.get("text") or ""
    new_doc, summary = _split_summary(text)

    return EditOutcome(
        new_document=new_doc,
        summary=summary,
        model=model,
        sources_used=tuple(sources),
        input_tokens=int(result.get("input_tokens") or 0),
        output_tokens=int(result.get("output_tokens") or 0),
        cost=float(result.get("cost") or 0.0),
    )


# ── Internals ───────────────────────────────────────────────────────────────


def _build_prompt(
    *,
    context: str,
    current_document: str,
    instruction: str,
    excerpts: str,
) -> str:
    parts: list[str] = []
    if context:
        parts.append(context.strip())
    parts.append("## Instruction\n" + instruction.strip())
    if excerpts:
        parts.append("## Source excerpts\nUse only these when evidence is needed.\n\n" + excerpts)
    parts.append(
        "## Current document\nReturn the full revised document below the line "
        "after applying the instruction. Remember to end with the `SUMMARY:` line.\n\n"
        + current_document
    )
    return "\n\n".join(parts)


def _build_excerpt_block(sources: tuple[str, ...]) -> str:
    if not sources:
        return ""
    blocks: list[str] = []
    for rel in sources:
        text = library.excerpt(rel)
        if not text:
            continue
        blocks.append(f"### {rel}\n{text}")
    return "\n\n".join(blocks)


def _split_summary(text: str) -> tuple[str, str]:
    """Split the model's reply into ``(document, summary)`` parts.

    The system prompt asks the model to end with ``SUMMARY: …`` on its own
    line; if the model skips that contract we fall back to using the whole
    output as the new document.
    """
    if not text:
        return "", ""
    lines = text.rstrip().splitlines()
    for idx in range(len(lines) - 1, -1, -1):
        line = lines[idx].strip()
        if line.upper().startswith("SUMMARY:"):
            summary = line.split(":", 1)[1].strip()
            doc_lines = lines[:idx]
            while doc_lines and not doc_lines[-1].strip():
                doc_lines.pop()
            return "\n".join(doc_lines), summary
    return text.rstrip(), ""


def _empty_outcome(model: str, error: str) -> EditOutcome:
    return EditOutcome(
        new_document="",
        summary="",
        model=model,
        sources_used=(),
        input_tokens=0,
        output_tokens=0,
        cost=0.0,
        error=error,
    )
