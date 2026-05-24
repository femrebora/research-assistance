"""Smoke test for the ra-originality Click command."""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner


@pytest.mark.unit
def test_cli_runs_with_minimal_args(tmp_path, monkeypatch):
    from research_assistant.verification import originality as orig

    draft = tmp_path / "draft.md"
    draft.write_text("Long enough paragraph. " * 30, encoding="utf-8")

    # Bypass all real I/O: every source returns no matches.
    monkeypatch.setattr(orig, "_internal_matches", lambda p, t: [])
    monkeypatch.setattr(orig, "_external_matches_openalex", lambda p, t: [])
    monkeypatch.setattr(orig, "_external_matches_crossref", lambda p, t: [])

    runner = CliRunner()
    result = runner.invoke(orig.main, [str(draft), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload == {"paragraphs": []}


@pytest.mark.unit
def test_cli_filters_sources(tmp_path, monkeypatch):
    from research_assistant.verification import originality as orig

    draft = tmp_path / "d.md"
    draft.write_text("Long enough paragraph. " * 30, encoding="utf-8")

    called = {"internal": 0, "openalex": 0, "crossref": 0}
    monkeypatch.setattr(orig, "_internal_matches",
                        lambda p, t: called.__setitem__("internal", called["internal"] + 1) or [])
    monkeypatch.setattr(orig, "_external_matches_openalex",
                        lambda p, t: called.__setitem__("openalex", called["openalex"] + 1) or [])
    monkeypatch.setattr(orig, "_external_matches_crossref",
                        lambda p, t: called.__setitem__("crossref", called["crossref"] + 1) or [])

    runner = CliRunner()
    result = runner.invoke(orig.main, [str(draft), "--sources", "openalex"])

    assert result.exit_code == 0, result.output
    assert called == {"internal": 0, "openalex": 1, "crossref": 0}
