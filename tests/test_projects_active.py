"""Tests for the active-project store in workspace/projects.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from research_assistant.workspace import projects as pj


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Point the project store at an isolated temp directory."""
    pdir = tmp_path / "projects"
    monkeypatch.setattr(pj, "PROJECTS_DIR", pdir)
    monkeypatch.setattr(pj, "_ACTIVE_FILE", pdir / ".active")
    return pdir


class TestActiveProject:
    def test_no_projects_returns_none(self, store):
        assert pj.get_active_slug() is None
        assert pj.get_active_project() is None

    def test_set_and_get_active(self, store):
        pj.create_project("My Thesis", research_question="Does X cause Y?")
        pj.set_active_slug("my-thesis")
        assert pj.get_active_slug() == "my-thesis"
        active = pj.get_active_project()
        assert active is not None
        assert active.slug == "my-thesis"
        assert active.research_question == "Does X cause Y?"

    def test_set_active_unknown_raises(self, store):
        with pytest.raises(FileNotFoundError):
            pj.set_active_slug("ghost")

    def test_fallback_to_most_recent_when_none_active(self, store):
        pj.create_project("First")
        pj.create_project("Second")
        # Nothing explicitly active -> most recently updated wins.
        active = pj.get_active_project()
        assert active is not None
        assert active.slug == "second"

    def test_deleting_active_clears_pointer(self, store):
        pj.create_project("Doomed")
        pj.set_active_slug("doomed")
        assert pj.get_active_slug() == "doomed"
        pj.delete_project("doomed")
        assert pj.get_active_slug() is None

    def test_stale_active_slug_falls_back(self, store):
        pj.create_project("Alpha")
        pj.set_active_slug("alpha")
        pj.delete_project("alpha")  # clears active
        pj.create_project("Beta")
        # active pointer gone; falls back to the remaining project
        active = pj.get_active_project()
        assert active is not None
        assert active.slug == "beta"
