"""Per-project thesis document — single Markdown file with one-step undo.

Each project owns one Markdown document at::

    THESIS_ROOT/projects/<slug>/document.md

A ``.prev`` sibling stores the version before the most recent change so
the user can revert one step. This is deliberately minimal — no version
history, no diff viewer, no autosave conflicts to fight.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from research_assistant.workspace.projects import PROJECTS_DIR, get_project, slugify

DEFAULT_DOC_TEMPLATE = (
    "# {title}\n\n"
    "_Created {created}_\n\n"
    "## Abstract\n\n"
    "Write or paste your abstract here.\n\n"
    "## Introduction\n\n"
    "Write or paste your introduction here.\n\n"
    "## Methods\n\n"
    "## Results\n\n"
    "## Discussion\n\n"
    "## Conclusion\n\n"
    "## References\n"
)


@dataclass(frozen=True)
class Document:
    """In-memory snapshot of the document on disk."""

    slug: str
    content: str
    path: str
    updated_at: str
    has_undo: bool
    chars: int


# ── Public API ──────────────────────────────────────────────────────────────


def doc_path(slug: str) -> Path:
    """Path to the project's document, even if the directory is missing."""
    safe = slugify(slug)
    return PROJECTS_DIR / safe / "document.md"


def load(slug: str) -> Document:
    """Load the project's document, creating a template on first access."""
    project = get_project(slug)
    if project is None:
        raise FileNotFoundError(f"Project '{slug}' not found.")

    path = doc_path(slug)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        seed = DEFAULT_DOC_TEMPLATE.format(
            title=project.title,
            created=datetime.now(tz=UTC).date().isoformat(),
        )
        path.write_text(seed, encoding="utf-8")

    content = path.read_text(encoding="utf-8")
    stat = path.stat()
    return Document(
        slug=project.slug,
        content=content,
        path=str(path),
        updated_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(timespec="seconds"),
        has_undo=_undo_path(path).exists(),
        chars=len(content),
    )


def save(slug: str, content: str) -> Document:
    """Persist new content, keeping the previous version as a ``.prev`` file.

    If ``content`` matches what's already on disk we skip the .prev rotation
    so a no-op save does not destroy a real undo step.
    """
    path = doc_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing != content:
            _undo_path(path).write_text(existing, encoding="utf-8")

    path.write_text(content, encoding="utf-8")
    return load(slug)


def undo(slug: str) -> Document:
    """Restore the previous version, if one exists. No-op otherwise."""
    path = doc_path(slug)
    prev = _undo_path(path)
    if not prev.exists():
        return load(slug)
    previous_content = prev.read_text(encoding="utf-8")
    # Swap: current becomes the prev so undo is itself undoable once.
    if path.exists():
        current = path.read_text(encoding="utf-8")
        prev.write_text(current, encoding="utf-8")
    else:
        prev.unlink(missing_ok=True)
    path.write_text(previous_content, encoding="utf-8")
    return load(slug)


# ── Internals ───────────────────────────────────────────────────────────────


def _undo_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".prev")
