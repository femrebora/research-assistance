"""Verify the dashboard tool catalog shows each tool's description."""
from __future__ import annotations

import pytest

from research_assistant.web.app import app
from research_assistant.web.tool_runner import TOOL_SPECS


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.mark.unit
def test_dashboard_shows_tool_descriptions(client):
    body = client.get("/").get_data(as_text=True)
    # First sentence of each description should appear (up to first ".")
    for spec in TOOL_SPECS:
        first_sentence = spec.description.split(".")[0].strip()
        if not first_sentence:
            continue
        # Truncated to 100 chars matches the template-side truncation we're about to add.
        snippet = first_sentence[:100]
        assert snippet in body, (
            f"Description for {spec.name} not found in dashboard."
        )
