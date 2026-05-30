"""Parse markdown drafts into named sections for the interactive workspace."""

from __future__ import annotations

import re

SECTION_KEY_MAP = {
    "abstract": "abstract",
    "introduction": "introduction",
    "methods": "methods",
    "results": "results",
    "discussion": "discussion",
    "conclusion": "conclusion",
    "conclusions": "conclusion",
}


def parse_sections(draft: str) -> list[dict]:
    """Split a markdown draft into sections keyed by heading.

    Returns a list of section dicts:
        {key, heading, content, score, ai_score, critique, version}
    """
    sections: list[dict] = []
    current: dict | None = None
    current_lines: list[str] = []

    for line in draft.split("\n"):
        if line.startswith("## ") or line.startswith("### "):
            if current is not None:
                current["content"] = "\n".join(current_lines)
                sections.append(current)

            heading = line.strip()
            heading_text = heading.lstrip("#").strip()
            canonical = _canonical_key(heading_text)

            current = {
                "key": canonical,
                "heading": heading,
                "content": "",
                "score": None,
                "ai_score": None,
                "critique": None,
                "version": 0,
            }
            current_lines = [line]
        elif current is not None:
            current_lines.append(line)
        elif line.strip():
            # Content before any section heading — preamble
            if not sections:
                preamble = {
                    "key": "preamble",
                    "heading": "# Preamble",
                    "content": line + "\n",
                    "score": None,
                    "ai_score": None,
                    "critique": None,
                    "version": 0,
                }
                sections.append(preamble)
            elif sections[0]["key"] == "preamble":
                sections[0]["content"] += line + "\n"

    if current is not None:
        current["content"] = "\n".join(current_lines)
        sections.append(current)

    return sections


def rebuild_draft(sections: list[dict]) -> str:
    """Rebuild a full markdown draft from its sections."""
    # Include preamble if present
    parts = []
    for s in sections:
        if s["key"] == "preamble":
            parts.append(s["content"].strip())
        else:
            parts.append(s["content"].strip())
    return "\n\n".join(parts) + "\n"


def get_section_by_key(sections: list[dict], key: str) -> dict | None:
    """Find a section by its canonical key."""
    for s in sections:
        if s["key"] == key:
            return s
    return None


def update_section(sections: list[dict], key: str, new_content: str, version: int | None = None):
    """Replace a section's content and bump its version."""
    for s in sections:
        if s["key"] == key:
            # Preserve the section heading line
            lines = new_content.strip().split("\n")
            if lines and lines[0].startswith("#"):
                s["heading"] = lines[0]
                s["content"] = "\n".join(lines)
            else:
                s["content"] = s["heading"] + "\n" + new_content
            if version is not None:
                s["version"] = version
            else:
                s["version"] += 1
            return True
    return False


def _canonical_key(heading_text: str) -> str:
    """Map a heading like '1. Introduction' or '## Abstract' to a canonical key."""
    # Strip leading numbers
    cleaned = re.sub(r"^\d+\.?\s*", "", heading_text).strip().lower()
    return SECTION_KEY_MAP.get(cleaned, cleaned.replace(" ", "_"))
