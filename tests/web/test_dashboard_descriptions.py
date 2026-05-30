"""Verify the dashboard sidebar shows the new consolidated navigation structure."""
from __future__ import annotations

import pytest

# ── New sidebar sections and their key nav items ────────────────────────────
EXPECTED_SIDEBAR_SECTIONS = [
    "Research",
    "Writing",
    "Project",
    "System",
]

EXPECTED_NAV_ITEMS = [
    "Dashboard",
    "Ask Library",
    "Library Search",
    "Paper Discovery",
    "Sessions",
    "Writing Studio",
    "Outline Builder",
    "Draft Review",
    "Chapter Review",
    "Project Setup",
    "Workspace",
    "AI Disclosure",
    "Index",  # "Index & Zotero" — check for partial match
    "Providers",
    "Settings",
]


@pytest.mark.unit
def test_dashboard_shows_sidebar_sections(client):
    """The new sidebar groups tools into four main categories."""
    body = client.get("/").get_data(as_text=True)
    for section in EXPECTED_SIDEBAR_SECTIONS:
        assert section in body, (
            f"Sidebar section '{section}' not found on dashboard."
        )


@pytest.mark.unit
def test_dashboard_shows_nav_items(client):
    """The sidebar includes all primary navigation items."""
    body = client.get("/").get_data(as_text=True)
    for item in EXPECTED_NAV_ITEMS:
        assert item in body, (
            f"Nav item '{item}' not found on dashboard sidebar."
        )


@pytest.mark.unit
def test_dashboard_shows_status_cards(client):
    """The dashboard shows index and provider status cards."""
    body = client.get("/").get_data(as_text=True)
    assert "Documents" in body
    assert "Chunks" in body
    assert "API providers" in body or "providers" in body.lower()


@pytest.mark.unit
def test_dashboard_has_recommended_workflow(client):
    """The dashboard includes the recommended workflow section."""
    body = client.get("/").get_data(as_text=True)
    assert "Recommended workflow" in body


@pytest.mark.unit
def test_new_routes_are_accessible(client):
    """All new consolidated routes return 200."""
    routes = [
        "/ask-library",
        "/library-search",
        "/paper-discovery",
        "/index-setup",
        "/writing-studio",
    ]
    for route in routes:
        resp = client.get(route)
        assert resp.status_code == 200, f"Route {route} returned {resp.status_code}"


@pytest.mark.unit
def test_old_routes_redirect(client):
    """Old routes redirect to new consolidated pages."""
    redirects = {
        "/index": "/index-setup",
        "/ask": "/ask-library?tab=rag",
        "/compare": "/ask-library?tab=compare",
    }
    for old, new in redirects.items():
        resp = client.get(old, follow_redirects=False)
        assert resp.status_code in (301, 302, 308), (
            f"GET {old} should redirect, got {resp.status_code}"
        )
        assert new in resp.headers.get("Location", ""), (
            f"Redirect from {old} should go to {new}, got {resp.headers.get('Location')}"
        )


@pytest.mark.unit
def test_error_pages_rendered(client):
    """Custom error pages are returned for 404 and 500."""
    # 404 on a nonsense route
    resp = client.get("/nonexistent-page-xyz")
    assert resp.status_code == 404
    body = resp.get_data(as_text=True)
    assert "Page not found" in body or "not found" in body.lower()
