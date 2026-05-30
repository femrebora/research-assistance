"""Workspace features for the research-assistant.

Adds the researcher-first workspace layer described in
``research_assistant_development_findings.txt``:

* :mod:`projects`  — per-project research context (Section 10)
* :mod:`telemetry` — model orchestration dashboard (Section 8)
* :mod:`prompts_library` — curated prompt library (Section 26)
* :mod:`peer_review` — multi-model AI peer review (Section 13)
* :mod:`defense`   — thesis defense simulator (Section 14)

These modules deliberately depend only on :mod:`research_assistant.common`
(plus the existing ``ask_model`` wrapper) so they can be reused both by the
CLI entry points and the Flask web UI.
"""
from __future__ import annotations

__all__ = [
    "defense",
    "peer_review",
    "projects",
    "prompts_library",
    "telemetry",
]
