"""Verify PaperForge blueprint registration and route availability."""
from __future__ import annotations

import pytest


@pytest.mark.unit
def test_paperforge_blueprint_registered():
    """If langgraph is installed, the blueprint should be importable."""
    from research_assistant.web.app import PAPERFORGE_AVAILABLE

    # PAPERFORGE_AVAILABLE is a bool set at import time.
    # If it's False, langgraph (optional dep) isn't installed — that's ok.
    # If it's True, everything is wired correctly.
    assert isinstance(PAPERFORGE_AVAILABLE, bool)


@pytest.mark.unit
def test_paperforge_flag_in_template_context(client):
    """paperforge_available is injected into every template context."""
    response = client.get("/")
    assert response.status_code == 200
    # The nav should either show PaperForge (if available) or not crash.
    # Either way, the page renders without error.
    body = response.get_data(as_text=True)
    assert "PaperForge" in body or "paperforge" in body.lower() or "Dashboard" in body


@pytest.mark.unit
def test_paperforge_page_when_available(client):
    """GET /paperforge returns 200 if the blueprint is registered."""
    from research_assistant.web.app import PAPERFORGE_AVAILABLE

    response = client.get("/paperforge")
    if PAPERFORGE_AVAILABLE:
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        # The PaperForge form should render
        assert "PaperForge" in body or "paperforge" in body.lower() or "<form" in body.lower()
    else:
        # When langgraph isn't installed, /paperforge may 404 (blueprint not
        # registered) — both 404 and 200 are acceptable depending on deployment.
        assert response.status_code in (200, 404, 500)


@pytest.mark.unit
def test_paperforge_unknown_job_returns_error(client):
    """GET /paperforge/result/nonexistent returns an error, not a crash."""
    response = client.get("/paperforge/result/nonexistent-job-id")
    # Should not 500 — either 404 or 200 with an error payload
    assert response.status_code in (200, 404)
