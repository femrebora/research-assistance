"""Verify the tools.html template renders Field.help for every field kind.

Rationale: tools.html currently only renders fld.help for checkbox fields
(see line 29 at HEAD). Help on textarea / select / number / text / file_or_text
is silently dropped. This test pins the correct behavior.
"""
from __future__ import annotations

import html

import pytest

from research_assistant.web.tool_runner import TOOL_SPECS


@pytest.mark.unit
def test_originality_tool_is_registered(client):
    from research_assistant.web.tool_runner import _MODULE_BY_NAME

    names = {s.name for s in TOOL_SPECS}
    assert "originality" in names, "originality not registered in TOOL_SPECS"
    assert _MODULE_BY_NAME.get("originality") == \
        "research_assistant.verification.originality"

    # The /tools/originality page should render and include the description.
    response = client.get("/tools/originality")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Originality" in body
    assert "OpenAlex" in body or "openalex" in body.lower()


@pytest.mark.unit
def test_help_renders_for_every_field_kind(client):
    """Every Field.help string appears in the rendered /tools/<name> page."""
    for spec in TOOL_SPECS:
        response = client.get(f"/tools/{spec.name}", follow_redirects=True)
        assert response.status_code == 200, f"{spec.name} returned {response.status_code}"
        body = response.get_data(as_text=True)
        # Unescape HTML entities for comparison
        unescaped_body = html.unescape(body)
        for fld in spec.fields:
            help_text = (fld.help or "").strip()
            if not help_text:
                continue
            assert help_text in unescaped_body, (
                f"Help text for {spec.name}.{fld.name} ({fld.kind}) "
                f"not rendered in /tools/{spec.name} page."
            )
