"""Project store — persistent, project-scoped research context.

Implements the "Project Memory" idea from Section 10 of
``research_assistant_development_findings.txt``:

    - thesis title
    - research question
    - hypothesis
    - keywords
    - preferred citation style
    - supervisor feedback / notes

Each project is a single JSON file under ``THESIS_ROOT/projects/<slug>.json``
so it is human-readable, git-friendly, and trivially backed up.

The store is intentionally minimal: it has no external dependencies and is
safe to call from both the CLI and the Flask layer. Heavier features
(embeddings, vector memory) can be layered on top later without changing
this interface.
"""
from __future__ import annotations

import contextlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from research_assistant.common import THESIS_ROOT

PROJECTS_DIR: Path = THESIS_ROOT / "projects"


# ── Data model ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Project:
    """An immutable snapshot of a research project's context.

    The dataclass is frozen so callers cannot mutate a project in place —
    use :func:`update_project` to write a new version, keeping the spirit of
    the global immutability rule in
    ``~/.claude/rules/common/coding-style.md``.
    """

    slug: str
    title: str
    research_question: str = ""
    hypothesis: str = ""
    keywords: tuple[str, ...] = field(default_factory=tuple)
    citation_style: str = "APA"
    supervisor_notes: str = ""
    discipline: str = ""
    created_at: str = ""
    updated_at: str = ""

    def as_dict(self) -> dict:
        """Return a JSON-serialisable dict (tuples → lists)."""
        data = asdict(self)
        data["keywords"] = list(self.keywords)
        return data


# ── Slug helpers ────────────────────────────────────────────────────────────


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Convert a title to a safe filesystem slug.

    Keeps a-z0-9, collapses everything else to ``-``. Strips leading/trailing
    dashes. Returns ``"project"`` for empty input so callers always get a
    usable name.
    """
    cleaned = _SLUG_RE.sub("-", (text or "").lower()).strip("-")
    return cleaned or "project"


def _project_path(slug: str) -> Path:
    """Path to a project file, rejecting traversal attempts."""
    safe = slugify(slug)
    return (PROJECTS_DIR / f"{safe}.json").resolve()


# ── CRUD ────────────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _ensure_dir() -> None:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def list_projects() -> list[Project]:
    """Return every project on disk, newest first."""
    _ensure_dir()
    items: list[Project] = []
    for path in PROJECTS_DIR.glob("*.json"):
        try:
            items.append(_load(path))
        except (OSError, json.JSONDecodeError, ValueError):
            # Skip corrupt files — never let one bad project break the list.
            continue
    items.sort(key=lambda p: p.updated_at or p.created_at, reverse=True)
    return items


def get_project(slug: str) -> Project | None:
    """Load a single project by slug, or ``None`` if it does not exist."""
    path = _project_path(slug)
    if not path.exists():
        return None
    try:
        return _load(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def create_project(
    title: str,
    *,
    research_question: str = "",
    hypothesis: str = "",
    keywords: tuple[str, ...] | list[str] = (),
    citation_style: str = "APA",
    supervisor_notes: str = "",
    discipline: str = "",
) -> Project:
    """Create a new project file. Raises ``FileExistsError`` on slug collision."""
    if not title.strip():
        raise ValueError("Project title cannot be empty.")
    slug = slugify(title)
    path = _project_path(slug)
    if path.exists():
        raise FileExistsError(f"Project '{slug}' already exists.")

    now = _now()
    project = Project(
        slug=slug,
        title=title.strip(),
        research_question=research_question.strip(),
        hypothesis=hypothesis.strip(),
        keywords=tuple(_normalise_keywords(keywords)),
        citation_style=citation_style.strip() or "APA",
        supervisor_notes=supervisor_notes.strip(),
        discipline=discipline.strip(),
        created_at=now,
        updated_at=now,
    )
    _save(project)
    return project


def update_project(slug: str, **changes) -> Project:
    """Update a project. Unknown keys are ignored. Returns the new snapshot."""
    existing = get_project(slug)
    if existing is None:
        raise FileNotFoundError(f"Project '{slug}' not found.")

    fields_ = {f.name for f in Project.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    payload = existing.as_dict()
    for key, value in changes.items():
        if key not in fields_ or key in {"slug", "created_at"}:
            continue
        if key == "keywords":
            payload[key] = list(_normalise_keywords(value))
        else:
            payload[key] = (value or "").strip() if isinstance(value, str) else value
    payload["updated_at"] = _now()
    project = _from_dict(payload)
    _save(project)
    return project


def delete_project(slug: str) -> bool:
    """Remove a project file. Returns ``True`` if something was removed."""
    path = _project_path(slug)
    if path.exists():
        path.unlink()
        if get_active_slug() == slugify(slug):
            _clear_active()
        return True
    return False


# ── Active project ────────────────────────────────────────────────────────────
#
# A single "active" project drives the dashboard banner and pre-fills the
# Outline Recommender. It is stored as one slug in a plain-text ``.active`` file
# so it is shared between the CLI and the web layer without a database.


_ACTIVE_FILE: Path = PROJECTS_DIR / ".active"


def set_active_slug(slug: str) -> None:
    """Mark a project as active. Raises ``FileNotFoundError`` if it is missing."""
    safe = slugify(slug)
    if get_project(safe) is None:
        raise FileNotFoundError(f"Project '{safe}' not found.")
    _ensure_dir()
    _ACTIVE_FILE.write_text(safe, encoding="utf-8")


def get_active_slug() -> str | None:
    """Return the active project's slug, or ``None`` if none is set."""
    try:
        slug = _ACTIVE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return slug or None


def _clear_active() -> None:
    with contextlib.suppress(OSError):
        _ACTIVE_FILE.unlink()


def get_active_project() -> Project | None:
    """Return the active project. Falls back to the most recently updated
    project when nothing is explicitly active, or ``None`` when there are no
    projects at all."""
    slug = get_active_slug()
    if slug:
        project = get_project(slug)
        if project is not None:
            return project
    projects = list_projects()
    return projects[0] if projects else None


# ── Helpers ─────────────────────────────────────────────────────────────────


def _normalise_keywords(value: tuple[str, ...] | list[str] | str) -> list[str]:
    """Accept tuple/list or comma/newline-separated string; dedupe + strip."""
    parts = re.split(r"[,\n]", value) if isinstance(value, str) else list(value)
    cleaned: list[str] = []
    seen: set[str] = set()
    for part in parts:
        token = part.strip()
        if token and token.lower() not in seen:
            cleaned.append(token)
            seen.add(token.lower())
    return cleaned


def _save(project: Project) -> None:
    _ensure_dir()
    path = _project_path(project.slug)
    path.write_text(
        json.dumps(project.as_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _load(path: Path) -> Project:
    data = json.loads(path.read_text(encoding="utf-8"))
    return _from_dict(data)


def _from_dict(data: dict) -> Project:
    return Project(
        slug=data.get("slug") or slugify(data.get("title", "")),
        title=data.get("title", ""),
        research_question=data.get("research_question", ""),
        hypothesis=data.get("hypothesis", ""),
        keywords=tuple(data.get("keywords") or ()),
        citation_style=data.get("citation_style", "APA"),
        supervisor_notes=data.get("supervisor_notes", ""),
        discipline=data.get("discipline", ""),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
    )


# ── Prompt context helper ───────────────────────────────────────────────────


def project_context_block(project: Project) -> str:
    """Render a project as a short system-prompt preamble.

    Used by peer-review, defense, and ask flows so any model can be primed
    with the current project's research question, keywords, and citation
    style without the caller having to assemble the prose by hand.
    """
    lines = [f"# Project: {project.title}"]
    if project.discipline:
        lines.append(f"Discipline: {project.discipline}")
    if project.research_question:
        lines.append(f"Research question: {project.research_question}")
    if project.hypothesis:
        lines.append(f"Hypothesis: {project.hypothesis}")
    if project.keywords:
        lines.append("Keywords: " + ", ".join(project.keywords))
    if project.citation_style:
        lines.append(f"Citation style: {project.citation_style}")
    if project.supervisor_notes:
        lines.append("Supervisor notes:\n" + project.supervisor_notes.strip())
    return "\n".join(lines)
