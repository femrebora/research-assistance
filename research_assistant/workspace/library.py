"""Local PDF library — list and excerpt PDFs from a plain folder.

The workspace can pull source context from two places:

* Zotero (already wired through ``researcher.py``)
* a plain local folder of PDFs, configurable via ``THESIS_DOCS``
  (default ``~/thesis``)

This module deliberately keeps things minimal: no indexing, no embeddings,
no Zotero metadata sync. It just lists files and pulls bounded text
excerpts on demand so an AI edit prompt can include them as context.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from research_assistant.common import THESIS_ROOT
from research_assistant.researcher import _extract_pdf_text

# Default folder for raw PDFs. Override via the env var; falls back to
# ``$THESIS_ROOT`` so a fresh install works without configuration.
DOCS_DIR: Path = Path(
    os.getenv("THESIS_DOCS")
    or os.getenv("THESIS_PDF_DIR")
    or str(THESIS_ROOT)
).expanduser()

# Per-document excerpt cap when feeding text into an AI edit prompt. Keeps
# total token usage predictable even when the user attaches many sources.
MAX_EXCERPT_CHARS = 4000


# ── Data model ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LocalPdf:
    """A PDF file found under :data:`DOCS_DIR`."""

    rel_path: str           # path relative to DOCS_DIR (used as the form value)
    name: str               # filename only, for display
    size_kb: int
    modified: str           # ISO date for sorting / display


# ── Public API ──────────────────────────────────────────────────────────────


def configured_root() -> Path:
    """Return the active local-PDF folder so the UI can show it to the user."""
    return DOCS_DIR


def list_pdfs(root: Path | None = None, *, limit: int = 200) -> list[LocalPdf]:
    """List PDFs under ``root`` (defaults to :data:`DOCS_DIR`).

    The result is sorted by modified-time, newest first, and capped at
    ``limit`` entries so the sidebar stays usable on a 5 000-PDF library.
    """
    base = (root or DOCS_DIR).expanduser()
    if not base.exists() or not base.is_dir():
        return []

    items: list[LocalPdf] = []
    for path in base.rglob("*.pdf"):
        try:
            stat = path.stat()
        except OSError:
            continue
        if not path.is_file():
            continue
        rel = path.relative_to(base).as_posix()
        items.append(
            LocalPdf(
                rel_path=rel,
                name=path.name,
                size_kb=max(1, stat.st_size // 1024),
                modified=_iso_date(stat.st_mtime),
            )
        )

    items.sort(key=lambda p: p.modified, reverse=True)
    return items[:limit]


def excerpt(rel_path: str, *, max_chars: int = MAX_EXCERPT_CHARS) -> str:
    """Return up to ``max_chars`` of plain text from a PDF inside the library.

    Path traversal is rejected — the resolved path must live inside the
    configured root. Returns an empty string if extraction fails.
    """
    safe_path = _resolve(rel_path)
    if safe_path is None or not safe_path.exists():
        return ""
    text = _extract_pdf_text(safe_path) or ""
    if not text:
        return ""
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip() + "\n…[truncated]"


def resolve(rel_path: str) -> Path | None:
    """Public wrapper around the internal path resolver."""
    return _resolve(rel_path)


# ── Internals ───────────────────────────────────────────────────────────────


def _resolve(rel_path: str) -> Path | None:
    """Resolve ``rel_path`` against :data:`DOCS_DIR`, rejecting escapes."""
    if not rel_path:
        return None
    candidate = (DOCS_DIR / rel_path).expanduser().resolve()
    root = DOCS_DIR.expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _iso_date(mtime: float) -> str:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(mtime, tz=UTC).isoformat(timespec="seconds")
