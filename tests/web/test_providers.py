"""Tests for the /providers page and /providers/test HTMX endpoint."""
from __future__ import annotations

import pytest


@pytest.mark.unit
def test_providers_page_renders(client):
    """GET /providers returns 200 and lists both API and CLI providers."""
    response = client.get("/providers")
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    # Page structure
    assert "Model providers" in body or "Providers" in body
    assert "API" in body
    assert "CLI" in body

    # At least one well-known provider name should appear
    assert any(name in body for name in ("Anthropic", "Gemini", "DeepSeek", "OpenAI"))


@pytest.mark.unit
def test_providers_test_unknown_alias(client):
    """POST /providers/test with a nonsense alias returns an error partial."""
    response = client.post("/providers/test", data={"alias": "nonexistent-model-xyz"})
    assert response.status_code == 200  # HTMX partial, not a redirect
    body = response.get_data(as_text=True)
    assert "Unknown" in body or "not found" in body.lower() or "error" in body.lower()


@pytest.mark.unit
def test_providers_test_valid_alias(client):
    """POST /providers/test with a known alias returns a result partial."""
    # claude-cli is a CLI alias that should exist when the CLI is installed
    response = client.post("/providers/test", data={"alias": "claude-cli"})
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    # The partial should contain either a success pill or an error message,
    # not a blank page
    assert len(body.strip()) > 0
    # At minimum the partial renders some kind of status indicator
    assert any(
        marker in body.lower()
        for marker in ("responded", "failed", "not found", "elapsed", "alias")
    )


@pytest.mark.unit
def test_providers_nav_link_exists(client):
    """The providers link appears in base.html nav (dashboards inherit it)."""
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'href="/providers"' in body
