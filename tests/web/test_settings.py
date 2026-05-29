"""Tests for the /settings page: render, save, and secret-write defense.

The settings page is a hybrid surface: secrets are read-only masked status,
while editable config keys (paths, CLI commands, timeouts) can be changed
and written back to .env. This test suite uses a temporary .env so the
real user config is never touched.
"""
from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from research_assistant.web.settings_store import (
    EDITABLE_FIELDS,
    SECRET_KEYS,
    editable_values,
    env_path,
    save,
    secret_status,
    validate,
)

# ---------------------------------------------------------------------------
# Unit tests (no Flask client needed)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_secret_keys_are_well_known():
    """Every critical secret key is in the denylist."""
    assert "ANTHROPIC_API_KEY" in SECRET_KEYS
    assert "GEMINI_API_KEY" in SECRET_KEYS
    assert "OPENAI_API_KEY" in SECRET_KEYS
    assert "DEEPSEEK_API_KEY" in SECRET_KEYS
    assert "FLASK_SECRET_KEY" in SECRET_KEYS
    assert "ZOTERO_API_KEY" in SECRET_KEYS


@pytest.mark.unit
def test_editable_fields_are_well_known():
    """Every intended editable field is in the allow-list."""
    keys = {f.key for f in EDITABLE_FIELDS}
    assert "THESIS_ROOT" in keys
    assert "CLI_TIMEOUT" in keys
    # At least one CLI_CMD should be editable
    assert any(k.endswith("_CLI_CMD") for k in keys)


@pytest.mark.unit
def test_validate_drops_secrets():
    """validate() silently removes any key not in the editable allow-list."""
    editable_keys = {f.key for f in EDITABLE_FIELDS}
    payload = {"THESIS_ROOT": "/tmp/test"}
    if "ANTHROPIC_API_KEY" not in editable_keys:
        payload["ANTHROPIC_API_KEY"] = "sk-injected"
    cleaned = validate(payload)
    assert "THESIS_ROOT" in cleaned
    assert "ANTHROPIC_API_KEY" not in cleaned


@pytest.mark.unit
def test_validate_rejects_non_numeric_timeout():
    """CLI_TIMEOUT must be a whole number."""
    with pytest.raises(ValueError, match="whole number"):
        validate({"CLI_TIMEOUT": "not-a-number"})


# ---------------------------------------------------------------------------
# Integration tests (temp .env round-trip)
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_dotenv():
    """Create a temporary .env file, patch env_path() to return it, clean up."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("ANTHROPIC_API_KEY=sk-test-secret-123\n")
        f.write("# a comment line\n")
        f.write("THESIS_ROOT=/tmp/thesis\n")
        f.write("\n")
        f.write("GEMINI_API_KEY=gk-other-secret\n")
        tmp_path = f.name

    with mock.patch(
        "research_assistant.web.settings_store.env_path", return_value=Path(tmp_path)
    ), mock.patch(
        "research_assistant.web.app.settings_store.env_path", return_value=Path(tmp_path)
    ):
        yield tmp_path

    # Cleanup
    with contextlib.suppress(OSError):
        os.unlink(tmp_path)


@pytest.mark.integration
def test_settings_page_renders(client):
    """GET /settings returns 200 with secret status and editable form."""
    response = client.get("/settings")
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert "Settings" in body or "settings" in body.lower()

    # Form should be present for editing
    assert "<form" in body.lower() or 'method="post"' in body.lower()


@pytest.mark.integration
def test_settings_post_saves_editable_and_preserves_secrets(temp_dotenv):
    """POST /settings saves editable keys; secrets are untouched."""
    client = _make_client()

    # Round-trip: save a new THESIS_ROOT
    response = client.post(
        "/settings",
        data={
            "THESIS_ROOT": "/tmp/new-thesis-path",
            # Attacker tries to inject a secret
            "ANTHROPIC_API_KEY": "sk-ATTACKER-INJECTED",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Read the .env file back
    saved = Path(temp_dotenv).read_text()

    # Editable key was updated
    assert "THESIS_ROOT=/tmp/new-thesis-path" in saved

    # Original secret was preserved verbatim
    assert "ANTHROPIC_API_KEY=sk-test-secret-123" in saved
    assert "GEMINI_API_KEY=gk-other-secret" in saved

    # Attacker injection was rejected
    assert "sk-ATTACKER-INJECTED" not in saved


@pytest.mark.integration
def test_settings_never_echoes_secrets(temp_dotenv):
    """GET /settings renders secret status pills, never the actual values."""
    client = _make_client()
    response = client.get("/settings")
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    # The secret value itself must NOT appear in the HTML
    assert "sk-test-secret-123" not in body
    assert "gk-other-secret" not in body

    # But the secret key name may appear as a label
    assert "ANTHROPIC_API_KEY" in body or "Anthropic" in body


@pytest.mark.integration
def test_settings_nav_link_exists(client):
    """The settings link appears in base.html nav."""
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'href="/settings"' in body


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client():
    """Return a Flask test client with TESTING mode on."""
    from research_assistant.web.app import app

    app.config["TESTING"] = True
    return app.test_client()
