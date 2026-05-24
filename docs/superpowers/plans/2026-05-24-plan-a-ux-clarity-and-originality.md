# Plan A: UX Clarity + Originality Check — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing UI clearer (descriptions and per-field help text rendered everywhere) and add a new "Originality check" tool that combines internal RAG matching with external academic search (OpenAlex + Crossref).

**Architecture:** Two additions on top of the existing Flask + HTMX + Tailwind UI and Click + pyzotero CLI. Part 1 is template-only changes plus filling in `Field.help` strings — no new modules. Part 2 adds two verification modules and a new `ToolSpec`, reusing the existing `verification/paraphrase_check.py` for the internal-similarity signal.

**Tech Stack:** Python 3.11+, Flask, Jinja2, Click, httpx, pytest, ruff. No new pip dependencies — `httpx` is already in `requirements.txt` and `shelve` is stdlib.

**Source spec:** `docs/superpowers/specs/2026-05-24-langgraph-agentic-pipeline-design.md` §12 and §13.

**Deferred to Plan C (Workbench):** §12 mentions `?` tooltip icons on the Workbench form and a Quick/Standard/Best mode-preset banner. These belong with Workbench itself and are NOT in Plan A.

---

## File Structure

**Create:**
- `research_assistant/verification/external_match.py` — OpenAlex + Crossref HTTP client with shelve-based response cache and polite rate-limiting
- `research_assistant/verification/originality.py` — orchestrator that runs internal + external checks and a Click CLI (`ra-originality`)
- `tests/verification/__init__.py` — empty, makes `tests/verification` a package
- `tests/verification/test_external_match.py`
- `tests/verification/test_originality.py`
- `tests/web/__init__.py` — empty
- `tests/web/test_tools_template.py`
- `tests/web/test_field_help_coverage.py`

**Modify:**
- `research_assistant/web/templates/tools.html` — render `Field.help` for every field kind
- `research_assistant/web/tool_runner.py` — populate `help=` on every `Field` in `TOOL_SPECS`; add `ToolSpec` for `originality`; add module mapping
- `research_assistant/web/templates/index.html` — show tool description under each tool in the catalog
- `research_assistant/web/templates/ask.html` — add `<details>` help blocks for the k and threshold sliders
- `research_assistant/web/templates/compare.html` — add `<details>` for the model selection rationale
- `pyproject.toml` — add `ra-originality` console script entry

---

## Conventions used throughout this plan

- **Commands assume CWD is the repo root:** `/home/emrebora/Downloads/research-assistant`.
- **Use the project virtualenv:** activate it first or prefix `python3 -m pytest …`.
- **One commit per task** at the end of each task's TDD cycle. Commit messages follow `<type>: <description>` (feat / fix / test / refactor / docs / chore).
- **All tests use `pytest`.** Run a single test with `python3 -m pytest tests/path/test.py::test_name -v`.
- **Lint after each part:** `python3 -m ruff check research_assistant/ tests/`.

---

# Part 1 — UX clarity quick-win (build step 1.5)

## Task 1: Add coverage test for `Field.help` on every TOOL_SPECS field

**Files:**
- Create: `tests/web/__init__.py`
- Create: `tests/web/test_field_help_coverage.py`

- [ ] **Step 1: Create the test package marker**

```python
# tests/web/__init__.py
```

(Empty file — its existence makes `tests/web/` a discoverable test package.)

- [ ] **Step 2: Write the failing coverage test**

```python
# tests/web/test_field_help_coverage.py
"""Enforce that every Field in TOOL_SPECS has a non-empty help string.

Rationale: helpful tooltips are an explicit UX requirement (spec §12).
A failing test here means a Field was added or modified without a help text.
"""
from __future__ import annotations

import pytest

from research_assistant.web.tool_runner import TOOL_SPECS


@pytest.mark.unit
def test_every_field_has_help_text():
    missing: list[str] = []
    for spec in TOOL_SPECS:
        for fld in spec.fields:
            if not (fld.help or "").strip():
                missing.append(f"{spec.name}.{fld.name}")
    assert not missing, (
        "Fields missing help text:\n  " + "\n  ".join(missing)
    )
```

- [ ] **Step 3: Run the test and watch it fail**

Run: `python3 -m pytest tests/web/test_field_help_coverage.py -v`

Expected: FAIL — dozens of fields are missing `help=`. The assertion message lists them all (e.g., `single_ask.prompt`, `zot.query`, `discover.query`, …).

- [ ] **Step 4: Commit the failing test only**

```bash
git add tests/web/__init__.py tests/web/test_field_help_coverage.py
git commit -m "test: add coverage test for Field.help across all TOOL_SPECS"
```

---

## Task 2: Fill in `Field.help` on every TOOL_SPECS field

**Files:**
- Modify: `research_assistant/web/tool_runner.py` — add `help="..."` to every `Field(...)` that lacks one

- [ ] **Step 1: Open `research_assistant/web/tool_runner.py` and add a `help=` to every Field that doesn't already have one.**

The list is long — work through `TOOL_SPECS` top to bottom. Use one-sentence, plain-English explanations. Examples for each field that's currently bare:

For `single_ask`:
```python
Field("prompt", "Question", "textarea", required=True, rows=4,
      placeholder="Explain MitoScape's filtering approach.",
      help="The question or instruction sent to the model. No document context is attached."),
Field("model", "Model", "select", flag="--model", default="claude", options_key="models",
      help="Which language model to ask. See README for cost / quality trade-offs per alias."),
Field("system", "System prompt (optional)", "textarea", flag="--system", rows=3,
      placeholder="You are a careful research assistant…",
      help="An optional system message that steers the model's tone / role."),
Field("temperature", "Temperature", "number", flag="--temperature", default=0.3,
      min=0.0, max=2.0, step=0.1,
      help="0 = deterministic, 1+ = creative. Keep low (≤0.4) for factual research."),
Field("raw", "Raw text output", "checkbox", flag="--raw",
      help="Skip the markdown renderer and print plain text — useful for piping."),
```

For `zot`:
```python
Field("query", "Query", "text", required=True, placeholder="NUMT contamination",
      help="Free-text search across titles, abstracts, tags, and authors of your Zotero library."),
Field("limit", "Max results", "number", flag="--limit", default=15, min=1, max=200, step=1,
      help="How many items to return at most."),
Field("collection", "Collection (optional)", "text", flag="--collection",
      placeholder="Chapter 1",
      help="Restrict search to a single Zotero collection by name (partial match)."),
Field("tag", "Tag (optional)", "text", flag="--tag",
      help="Restrict to a single Zotero tag."),
Field("bib", "Citekeys only", "checkbox", flag="--bib",
      help="Output only citekeys (one per line), suitable for piping into LaTeX or .bib filters."),
Field("export_format", "Export format", "select", flag="--export",
      default="", options=("", "bibtex", "json"),
      help="Export the result set as BibTeX or JSON instead of the default table."),
```

Continue for `discover`, `evidence`, `ideas`, `outline`, `critique`, `critic`, `paraphrase`, `coherence`, `paraphrase_check`, `audit`, `verify`, `claim_verify`, `pipeline`, `disclose`. Read each field, look at its `--help` text in the actual CLI module for inspiration if you need it (`grep -n "help=" research_assistant/research/discover.py`, etc.), and write one plain sentence.

**Rule of thumb:** if you'd hesitate before answering "what does this do?", the help text isn't clear enough. Aim for under 120 characters per line.

- [ ] **Step 2: Run the coverage test again**

Run: `python3 -m pytest tests/web/test_field_help_coverage.py -v`

Expected: PASS. If any field is still missing, the assertion message tells you which.

- [ ] **Step 3: Run the full test suite to confirm nothing else broke**

Run: `python3 -m pytest -q`

Expected: 111 passed (the original 110 + this new one).

- [ ] **Step 4: Lint**

Run: `python3 -m ruff check research_assistant/web/tool_runner.py`

Expected: All checks passed.

- [ ] **Step 5: Commit**

```bash
git add research_assistant/web/tool_runner.py
git commit -m "feat(ui): add plain-English help text to every TOOL_SPECS field"
```

---

## Task 3: Render `Field.help` for every field kind in `tools.html`

**Files:**
- Create: `tests/web/test_tools_template.py`
- Modify: `research_assistant/web/templates/tools.html` — add help-rendering blocks for non-checkbox field kinds

- [ ] **Step 1: Write a failing template-rendering test**

```python
# tests/web/test_tools_template.py
"""Verify the tools.html template renders Field.help for every field kind.

Rationale: tools.html currently only renders fld.help for checkbox fields
(see line 29 at HEAD). Help on textarea / select / number / text / file_or_text
is silently dropped. This test pins the correct behavior.
"""
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
def test_help_renders_for_every_field_kind(client):
    """Every Field.help string appears in the rendered /tools/<name> page."""
    for spec in TOOL_SPECS:
        response = client.get(f"/tools/{spec.name}")
        assert response.status_code == 200, f"{spec.name} 404"
        body = response.get_data(as_text=True)
        for fld in spec.fields:
            help_text = (fld.help or "").strip()
            if not help_text:
                continue
            assert help_text in body, (
                f"Help text for {spec.name}.{fld.name} ({fld.kind}) "
                f"not rendered in /tools/{spec.name} page."
            )
```

- [ ] **Step 2: Run the test and watch it fail**

Run: `python3 -m pytest tests/web/test_tools_template.py -v`

Expected: FAIL on the first non-checkbox field with help — assertion shows e.g. `Help text for single_ask.prompt (textarea) not rendered`.

- [ ] **Step 3: Update `tools.html` so every field kind renders `fld.help`**

In `research_assistant/web/templates/tools.html`, after the closing tag of each non-checkbox field block, add the same help-paragraph the checkbox branch already uses. The pattern is:

```jinja
{% if fld.help %}<p class="text-xs text-slate-500 mt-1">{{ fld.help }}</p>{% endif %}
```

Concretely, the file's edit points are:

**After the `file_or_text` block** (just after the closing `</div>` of the path input row, before the outer `{% elif fld.kind == "textarea" %}`):

```jinja
                {% if fld.help %}<p class="text-xs text-slate-500 mt-1">{{ fld.help }}</p>{% endif %}
```

**After the `textarea` block** (after `</textarea>`, before `{% elif fld.kind == "select" %}`):

```jinja
                {% if fld.help %}<p class="text-xs text-slate-500 mt-1">{{ fld.help }}</p>{% endif %}
```

**After the `select` block** (after `</select>`, before `{% elif fld.kind == "number" %}`):

```jinja
                {% if fld.help %}<p class="text-xs text-slate-500 mt-1">{{ fld.help }}</p>{% endif %}
```

**After the `number` `<input>` (number field has no closing tag, just self-closing):**

```jinja
                {% if fld.help %}<p class="text-xs text-slate-500 mt-1">{{ fld.help }}</p>{% endif %}
```

**After the default `text` `<input>`** (the final `{% else %}` branch):

```jinja
                {% if fld.help %}<p class="text-xs text-slate-500 mt-1">{{ fld.help }}</p>{% endif %}
```

- [ ] **Step 4: Run the test, watch it pass**

Run: `python3 -m pytest tests/web/test_tools_template.py -v`

Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `python3 -m pytest -q`

Expected: 112 passed.

- [ ] **Step 6: Commit**

```bash
git add research_assistant/web/templates/tools.html tests/web/test_tools_template.py
git commit -m "feat(ui): render Field.help for every field kind in tools.html"
```

---

## Task 4: Show tool descriptions on the dashboard tool catalog

**Files:**
- Modify: `research_assistant/web/templates/index.html` — show `spec.description` (truncated) under each tool name in the catalog block
- Create: `tests/web/test_dashboard_descriptions.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_dashboard_descriptions.py
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
```

- [ ] **Step 2: Run, watch it fail**

Run: `python3 -m pytest tests/web/test_dashboard_descriptions.py -v`

Expected: FAIL — descriptions not rendered on the dashboard.

- [ ] **Step 3: Find the tool catalog block in `index.html`**

Run: `grep -n "tool_groups\|spec.label" research_assistant/web/templates/index.html`

You should see the loop that renders the catalog (something like `{% for category, specs in tool_groups.items() %}` followed by an inner `{% for spec in specs %}`).

- [ ] **Step 4: Add a description snippet under each `spec.label` in that loop**

Below the line that renders `spec.label` (typically wrapped in an `<a>` or `<div>`), add:

```jinja
<p class="text-xs text-slate-500 mt-0.5">{{ (spec.description.split('.')[0]|truncate(100, True, '')) }}</p>
```

(The `truncate` filter clips to 100 chars; the first-sentence split keeps it short.)

- [ ] **Step 5: Run test, watch it pass**

Run: `python3 -m pytest tests/web/test_dashboard_descriptions.py -v`

Expected: PASS.

- [ ] **Step 6: Manually sanity-check**

Run: `python3 -m research_assistant.web.app &  sleep 1 ; curl -s http://127.0.0.1:5050/ | grep -c "text-slate-500"`

Expected: a non-zero count (many `text-slate-500` instances appear, including the new descriptions). Kill the dev server with `kill %1`.

- [ ] **Step 7: Commit**

```bash
git add research_assistant/web/templates/index.html tests/web/test_dashboard_descriptions.py
git commit -m "feat(ui): show tool descriptions on the dashboard catalog"
```

---

## Task 5: Add `<details>` help blocks on `/ask` for k and threshold

**Files:**
- Modify: `research_assistant/web/templates/ask.html`

- [ ] **Step 1: Open `research_assistant/web/templates/ask.html` and locate the k and threshold sliders**

The relevant lines are around 32-43 (look for `name="k"` and `name="threshold"`).

- [ ] **Step 2: Add an explanation `<details>` element under each slider**

After the threshold input's outer `</div>` (before the "Save as" column), add a row-spanning paragraph:

```jinja
        <div class="md:col-span-4 -mt-1">
            <details class="text-xs text-slate-500 cursor-pointer select-none">
                <summary class="text-slate-600 hover:text-slate-800">What do k and threshold mean?</summary>
                <p class="mt-1 leading-relaxed">
                    <strong>k</strong> is the maximum number of source chunks retrieved from your indexed library
                    before the model writes its answer. Higher k = more context but more cost &amp; potential noise.
                    <br>
                    <strong>Threshold</strong> is the minimum cosine similarity a chunk must have to be included.
                    Higher threshold = stricter filter, fewer chunks. Drop it to 0.2-0.3 if you keep seeing
                    "No sufficiently relevant passages found".
                </p>
            </details>
        </div>
```

- [ ] **Step 3: Verify in browser (optional sanity)**

Run: `python3 -m research_assistant.web.app & sleep 1 ; curl -s http://127.0.0.1:5050/ask | grep -c "What do k and threshold"`

Expected: 1. Kill: `kill %1`.

- [ ] **Step 4: Run the full suite to confirm no template error**

Run: `python3 -m pytest -q`

Expected: 113 passed (still rising).

- [ ] **Step 5: Commit**

```bash
git add research_assistant/web/templates/ask.html
git commit -m "feat(ui): add inline help for k and threshold sliders on /ask"
```

---

## Task 6: Add `<details>` help block on `/compare` for the model picker

**Files:**
- Modify: `research_assistant/web/templates/compare.html`

- [ ] **Step 1: Open `research_assistant/web/templates/compare.html` and locate the models checkbox group**

Look for `name="models"` or the section that lets the user pick which models to compare.

- [ ] **Step 2: Add a `<details>` element just below the model list**

```jinja
<details class="text-xs text-slate-500 cursor-pointer select-none mt-2">
    <summary class="text-slate-600 hover:text-slate-800">When should I pick which models?</summary>
    <p class="mt-1 leading-relaxed">
        Pick 2–4 models from different families to surface disagreements.
        <strong>Claude</strong> and <strong>GPT</strong> are strong on prose;
        <strong>Gemini</strong> is strong on multi-document synthesis;
        <strong>DeepSeek</strong> is cheap and good at structured tasks;
        <strong>Sonnet/Haiku/Flash/gpt-mini</strong> are faster + cheaper variants for high-volume use.
        With <em>--rag</em> on, all models see the same retrieved context — so disagreement is about
        interpretation, not access.
    </p>
</details>
```

- [ ] **Step 3: Run the suite**

Run: `python3 -m pytest -q`

Expected: 113 passed (template change, no new test).

- [ ] **Step 4: Commit**

```bash
git add research_assistant/web/templates/compare.html
git commit -m "feat(ui): add inline help for model selection on /compare"
```

---

## Task 7: Final Part-1 lint pass

- [ ] **Step 1: Lint everything modified**

Run: `python3 -m ruff check research_assistant/ tests/`

Expected: All checks passed.

- [ ] **Step 2: Run the full suite one more time**

Run: `python3 -m pytest -q`

Expected: 113 passed.

Part 1 ships value on its own — every existing UI page is now better-explained.

---

# Part 2 — Originality check (build step 2.5)

## Task 8: Create `external_match.py` skeleton with cache key generation

**Files:**
- Create: `research_assistant/verification/external_match.py`
- Create: `tests/verification/__init__.py`
- Create: `tests/verification/test_external_match.py`

- [ ] **Step 1: Create the test package marker**

```python
# tests/verification/__init__.py
```

- [ ] **Step 2: Write the first failing test — cache key is stable and source-aware**

```python
# tests/verification/test_external_match.py
"""Unit tests for verification.external_match: OpenAlex + Crossref clients."""
from __future__ import annotations

import pytest


@pytest.mark.unit
def test_cache_key_is_stable_and_source_aware():
    from research_assistant.verification.external_match import _cache_key

    k1 = _cache_key("openalex", "NUMT filtering")
    k2 = _cache_key("openalex", "NUMT filtering")
    k3 = _cache_key("crossref", "NUMT filtering")
    k4 = _cache_key("openalex", "Different query")

    assert k1 == k2, "Same source+query must produce the same key"
    assert k1 != k3, "Different source must produce a different key"
    assert k1 != k4, "Different query must produce a different key"
    assert isinstance(k1, str) and len(k1) == 64, "Cache key should be hex sha256"
```

- [ ] **Step 3: Create the module with the minimal helper**

```python
# research_assistant/verification/external_match.py
"""HTTP clients for OpenAlex and Crossref with a shelve-based response cache.

Used by the Originality check tool to compare draft paragraphs against
published academic abstracts.  The clients are intentionally simple: paginated
JSON requests, polite rate-limit, 24-hour cached responses.
"""
from __future__ import annotations

import hashlib


def _cache_key(source: str, query: str) -> str:
    """Stable cache key for a (source, query) pair. Hex sha256."""
    h = hashlib.sha256()
    h.update(source.encode("utf-8"))
    h.update(b"\x00")
    h.update(query.encode("utf-8"))
    return h.hexdigest()
```

- [ ] **Step 4: Run the test, watch it pass**

Run: `python3 -m pytest tests/verification/test_external_match.py::test_cache_key_is_stable_and_source_aware -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research_assistant/verification/external_match.py \
        tests/verification/__init__.py \
        tests/verification/test_external_match.py
git commit -m "feat(verification): add external_match cache key skeleton"
```

---

## Task 9: Add OpenAlex search with mocked HTTP

**Files:**
- Modify: `research_assistant/verification/external_match.py`
- Modify: `tests/verification/test_external_match.py`

- [ ] **Step 1: Write the failing test (OpenAlex client returns parsed matches from mocked JSON)**

Append to `tests/verification/test_external_match.py`:

```python
from unittest.mock import patch

OPENALEX_FIXTURE = {
    "results": [
        {
            "id": "https://openalex.org/W123",
            "title": "NUMT contamination in clinical mtDNA sequencing",
            "abstract_inverted_index": {"NUMT": [0], "contamination": [1], "is": [2], "common": [3]},
            "publication_year": 2024,
            "doi": "https://doi.org/10.1234/example",
            "authorships": [{"author": {"display_name": "Doe, Jane"}}],
        }
    ]
}


@pytest.mark.unit
def test_search_openalex_returns_parsed_matches():
    from research_assistant.verification.external_match import search_openalex

    fake_response = type("R", (), {"json": lambda self: OPENALEX_FIXTURE, "raise_for_status": lambda self: None})()
    with patch("research_assistant.verification.external_match.httpx.get", return_value=fake_response):
        results = search_openalex("NUMT contamination in clinical mtDNA", limit=5)

    assert len(results) == 1
    m = results[0]
    assert m["title"].startswith("NUMT contamination")
    assert m["year"] == 2024
    assert m["doi"] == "10.1234/example"             # bare DOI, no URL prefix
    assert m["authors"] == "Doe, Jane"
    assert "NUMT contamination is common" in m["abstract"]
    assert m["url"] == "https://openalex.org/W123"
```

- [ ] **Step 2: Run, watch it fail**

Run: `python3 -m pytest tests/verification/test_external_match.py::test_search_openalex_returns_parsed_matches -v`

Expected: FAIL — `search_openalex` doesn't exist.

- [ ] **Step 3: Implement `search_openalex`**

Append to `research_assistant/verification/external_match.py`:

```python
import os
from typing import Any

import httpx

OPENALEX_BASE_URL = "https://api.openalex.org/works"
HTTP_TIMEOUT = 20.0


def _polite_pool_params() -> dict[str, str]:
    email = os.getenv("OPENALEX_EMAIL") or os.getenv("CONTACT_EMAIL")
    return {"mailto": email} if email else {}


def _reconstruct_abstract(inverted: dict[str, list[int]] | None) -> str:
    """OpenAlex returns abstracts as `{word: [positions]}` — flatten back to text."""
    if not inverted:
        return ""
    positions: dict[int, str] = {}
    for word, idxs in inverted.items():
        for i in idxs:
            positions[i] = word
    return " ".join(positions[i] for i in sorted(positions))


def _strip_doi_prefix(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace("https://doi.org/", "")


def _first_author(authorships: list[dict[str, Any]]) -> str | None:
    if not authorships:
        return None
    name = authorships[0].get("author", {}).get("display_name")
    return name or None


def search_openalex(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Search OpenAlex /works. Returns a list of dicts with title/abstract/year/doi/authors/url.

    Network errors and non-2xx responses are caught and yield an empty list — the
    caller (originality.py) is tolerant of this.
    """
    params = {"search": query, "per-page": str(limit), **_polite_pool_params()}
    try:
        response = httpx.get(OPENALEX_BASE_URL, params=params, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for work in payload.get("results", []):
        out.append(
            {
                "title": work.get("title", "") or "",
                "abstract": _reconstruct_abstract(work.get("abstract_inverted_index")),
                "year": work.get("publication_year"),
                "doi": _strip_doi_prefix(work.get("doi")),
                "authors": _first_author(work.get("authorships", [])),
                "url": work.get("id"),
            }
        )
    return out
```

- [ ] **Step 4: Run test, watch it pass**

Run: `python3 -m pytest tests/verification/test_external_match.py::test_search_openalex_returns_parsed_matches -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research_assistant/verification/external_match.py tests/verification/test_external_match.py
git commit -m "feat(verification): add OpenAlex search to external_match"
```

---

## Task 10: Add Crossref search with mocked HTTP

**Files:**
- Modify: `research_assistant/verification/external_match.py`
- Modify: `tests/verification/test_external_match.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/verification/test_external_match.py`:

```python
CROSSREF_FIXTURE = {
    "message": {
        "items": [
            {
                "DOI": "10.5678/another",
                "title": ["A second NUMT study"],
                "abstract": "<jats:p>NUMTs interfere with variant calling.</jats:p>",
                "issued": {"date-parts": [[2023]]},
                "author": [{"given": "Alice", "family": "Smith"}],
                "URL": "https://doi.org/10.5678/another",
            }
        ]
    }
}


@pytest.mark.unit
def test_search_crossref_returns_parsed_matches():
    from research_assistant.verification.external_match import search_crossref

    fake = type("R", (), {"json": lambda self: CROSSREF_FIXTURE, "raise_for_status": lambda self: None})()
    with patch("research_assistant.verification.external_match.httpx.get", return_value=fake):
        results = search_crossref("NUMT interfere variant calling", limit=5)

    assert len(results) == 1
    m = results[0]
    assert m["title"] == "A second NUMT study"
    assert m["year"] == 2023
    assert m["doi"] == "10.5678/another"
    assert m["authors"] == "Smith, Alice"
    assert "NUMTs interfere with variant calling." in m["abstract"]   # JATS stripped
    assert m["url"] == "https://doi.org/10.5678/another"
```

- [ ] **Step 2: Run, fail**

Run: `python3 -m pytest tests/verification/test_external_match.py::test_search_crossref_returns_parsed_matches -v`

Expected: FAIL — `search_crossref` doesn't exist.

- [ ] **Step 3: Implement Crossref**

Append to `research_assistant/verification/external_match.py`:

```python
import re

CROSSREF_BASE_URL = "https://api.crossref.org/works"


def _strip_jats(html: str | None) -> str:
    """Crossref abstracts are wrapped in JATS XML tags. Strip them for cosine matching."""
    if not html:
        return ""
    return re.sub(r"<[^>]+>", "", html).strip()


def _crossref_authors(author_list: list[dict[str, Any]] | None) -> str | None:
    if not author_list:
        return None
    a = author_list[0]
    family = a.get("family", "")
    given = a.get("given", "")
    if family and given:
        return f"{family}, {given}"
    return family or given or None


def _crossref_year(issued: dict[str, Any] | None) -> int | None:
    if not issued:
        return None
    parts = issued.get("date-parts") or [[None]]
    if not parts or not parts[0]:
        return None
    year = parts[0][0]
    return int(year) if isinstance(year, int) else None


def search_crossref(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Search Crossref /works. Same return shape as search_openalex."""
    params = {
        "query.bibliographic": query,
        "rows": str(limit),
        "select": "DOI,title,abstract,issued,author,URL",
    }
    try:
        response = httpx.get(CROSSREF_BASE_URL, params=params, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for item in payload.get("message", {}).get("items", []):
        title_list = item.get("title") or []
        out.append(
            {
                "title": title_list[0] if title_list else "",
                "abstract": _strip_jats(item.get("abstract")),
                "year": _crossref_year(item.get("issued")),
                "doi": item.get("DOI"),
                "authors": _crossref_authors(item.get("author")),
                "url": item.get("URL"),
            }
        )
    return out
```

- [ ] **Step 4: Run, pass**

Run: `python3 -m pytest tests/verification/test_external_match.py::test_search_crossref_returns_parsed_matches -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research_assistant/verification/external_match.py tests/verification/test_external_match.py
git commit -m "feat(verification): add Crossref search to external_match"
```

---

## Task 11: Add shelve-based response cache with TTL

**Files:**
- Modify: `research_assistant/verification/external_match.py`
- Modify: `tests/verification/test_external_match.py`

- [ ] **Step 1: Write the failing cache test**

Append to `tests/verification/test_external_match.py`:

```python
import time
from pathlib import Path


@pytest.mark.unit
def test_cached_search_hits_cache_on_second_call(tmp_path, monkeypatch):
    """Two identical search calls should make exactly one HTTP request."""
    from research_assistant.verification import external_match as em

    monkeypatch.setattr(em, "CACHE_PATH", tmp_path / "test_cache.shelf")

    call_count = {"n": 0}

    def fake_get(url, params=None, timeout=None):
        call_count["n"] += 1
        return type("R", (), {"json": lambda self: OPENALEX_FIXTURE, "raise_for_status": lambda self: None})()

    monkeypatch.setattr(em.httpx, "get", fake_get)

    r1 = em.cached_search("openalex", "NUMT contamination", limit=5)
    r2 = em.cached_search("openalex", "NUMT contamination", limit=5)

    assert call_count["n"] == 1, "Second call should hit cache, not HTTP"
    assert r1 == r2


@pytest.mark.unit
def test_cache_expires_after_ttl(tmp_path, monkeypatch):
    from research_assistant.verification import external_match as em

    monkeypatch.setattr(em, "CACHE_PATH", tmp_path / "test_cache.shelf")
    monkeypatch.setattr(em, "CACHE_TTL_SECONDS", 0)  # immediate expiry

    call_count = {"n": 0}

    def fake_get(*a, **kw):
        call_count["n"] += 1
        return type("R", (), {"json": lambda self: OPENALEX_FIXTURE, "raise_for_status": lambda self: None})()

    monkeypatch.setattr(em.httpx, "get", fake_get)

    em.cached_search("openalex", "NUMT", limit=5)
    em.cached_search("openalex", "NUMT", limit=5)
    assert call_count["n"] == 2, "Expired cache should force a refetch"
```

- [ ] **Step 2: Run, fail**

Run: `python3 -m pytest tests/verification/test_external_match.py -k cache -v`

Expected: FAIL — `cached_search` and `CACHE_PATH` don't exist.

- [ ] **Step 3: Implement the cache**

Append to `research_assistant/verification/external_match.py`:

```python
import shelve
import time
from pathlib import Path

CACHE_PATH: Path = Path.home() / ".cache" / "research-assistant" / "external_match.shelf"
CACHE_TTL_SECONDS: int = 24 * 60 * 60  # 24 hours

_SEARCHERS = {
    "openalex": search_openalex,
    "crossref": search_crossref,
}


def cached_search(source: str, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Run `_SEARCHERS[source](query, limit=limit)` with on-disk caching.

    Cache entries are pickled `{ts, results}` dicts. Entries older than
    CACHE_TTL_SECONDS are refetched. Cache failures are non-fatal — we fall
    back to a live request.
    """
    if source not in _SEARCHERS:
        raise ValueError(f"Unknown source '{source}'. Available: {list(_SEARCHERS)}")

    key = _cache_key(source, f"{query}::{limit}")
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        with shelve.open(str(CACHE_PATH)) as cache:
            entry = cache.get(key)
            if entry and (time.time() - entry["ts"] < CACHE_TTL_SECONDS):
                return entry["results"]
    except Exception:
        pass  # cache miss / corruption — fall through to live fetch

    results = _SEARCHERS[source](query, limit=limit)

    try:
        with shelve.open(str(CACHE_PATH)) as cache:
            cache[key] = {"ts": time.time(), "results": results}
    except Exception:
        pass  # write failure is non-fatal

    return results
```

- [ ] **Step 4: Run cache tests, pass**

Run: `python3 -m pytest tests/verification/test_external_match.py -k cache -v`

Expected: PASS (2 tests).

- [ ] **Step 5: Run the whole external_match suite**

Run: `python3 -m pytest tests/verification/test_external_match.py -v`

Expected: 4 PASS (cache_key + openalex + crossref + 2 cache tests).

- [ ] **Step 6: Commit**

```bash
git add research_assistant/verification/external_match.py tests/verification/test_external_match.py
git commit -m "feat(verification): add 24h shelve cache to external_match"
```

---

## Task 12: Define `OriginalityReport` schemas and the orchestrator skeleton

**Files:**
- Create: `research_assistant/verification/originality.py`
- Create: `tests/verification/test_originality.py`

- [ ] **Step 1: Write the failing schema test**

```python
# tests/verification/test_originality.py
"""Tests for verification.originality."""
from __future__ import annotations

import pytest


@pytest.mark.unit
def test_paragraph_report_severity_thresholds():
    from research_assistant.verification.originality import ExternalMatch, ParagraphReport

    clean = ParagraphReport(index=0, text="x" * 200, matches=[])
    assert clean.severity == "green"

    m_yellow = ExternalMatch(
        source="openalex", similarity=0.85, title="t", authors=None, year=None,
        doi=None, citekey=None, excerpt="", url=None,
    )
    yellow = ParagraphReport(index=1, text="x" * 200, matches=[m_yellow])
    assert yellow.severity == "yellow"

    m_red = m_yellow.model_copy(update={"similarity": 0.95})
    red = ParagraphReport(index=2, text="x" * 200, matches=[m_red])
    assert red.severity == "red"


@pytest.mark.unit
def test_originality_report_summary():
    from research_assistant.verification.originality import (
        ExternalMatch, OriginalityReport, ParagraphReport,
    )

    matches_red = [ExternalMatch(
        source="internal", similarity=0.95, title="t", authors=None, year=None,
        doi=None, citekey="smith2024", excerpt="", url=None,
    )]
    matches_yellow = [ExternalMatch(
        source="openalex", similarity=0.82, title="t", authors=None, year=None,
        doi=None, citekey=None, excerpt="", url=None,
    )]

    report = OriginalityReport(paragraphs=[
        ParagraphReport(index=0, text="x" * 200, matches=matches_red),
        ParagraphReport(index=1, text="x" * 200, matches=matches_yellow),
        ParagraphReport(index=2, text="x" * 200, matches=[]),
    ])
    assert report.summary == "1 red flag(s), 1 yellow flag(s)"
```

- [ ] **Step 2: Run, fail**

Run: `python3 -m pytest tests/verification/test_originality.py -v`

Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Create the module with schemas**

```python
# research_assistant/verification/originality.py
"""Originality check: combines internal RAG similarity with external academic search.

NOT a true plagiarism detector. Produces leads for human review.

Usage:
    ra-originality drafts/ch1.md
    ra-originality drafts/ch1.md --sources internal,openalex --internal-threshold 0.80
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ExternalMatch(BaseModel):
    """A single match for a paragraph from one source."""

    source: Literal["internal", "openalex", "crossref"]
    similarity: float
    title: str
    authors: str | None = None
    year: int | None = None
    doi: str | None = None
    citekey: str | None = None         # only for internal matches
    excerpt: str = ""                  # snippet that matched
    url: str | None = None


class ParagraphReport(BaseModel):
    index: int
    text: str
    matches: list[ExternalMatch]

    @property
    def severity(self) -> Literal["green", "yellow", "red"]:
        if not self.matches:
            return "green"
        max_sim = max(m.similarity for m in self.matches)
        return "red" if max_sim >= 0.92 else "yellow"


class OriginalityReport(BaseModel):
    paragraphs: list[ParagraphReport]

    @property
    def summary(self) -> str:
        red = sum(1 for p in self.paragraphs if p.severity == "red")
        yellow = sum(1 for p in self.paragraphs if p.severity == "yellow")
        return f"{red} red flag(s), {yellow} yellow flag(s)"
```

- [ ] **Step 4: Run, pass**

Run: `python3 -m pytest tests/verification/test_originality.py -v`

Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add research_assistant/verification/originality.py tests/verification/test_originality.py
git commit -m "feat(verification): add OriginalityReport / ParagraphReport / ExternalMatch schemas"
```

---

## Task 13: Implement `check_originality` with all three sources

**Files:**
- Modify: `research_assistant/verification/originality.py`
- Modify: `tests/verification/test_originality.py`

- [ ] **Step 1: Write the failing orchestrator test**

Append to `tests/verification/test_originality.py`:

```python
from unittest.mock import patch


@pytest.mark.unit
def test_check_originality_runs_internal_and_external(tmp_path, monkeypatch):
    """Given a draft with two paragraphs, check_originality runs the requested
    sources and aggregates matches into ParagraphReport entries."""
    from research_assistant.verification import originality as orig

    draft = tmp_path / "draft.md"
    draft.write_text(
        "First paragraph. " * 30 + "\n\n" + "Second paragraph. " * 30,
        encoding="utf-8",
    )

    # Fake the three source helpers
    def fake_internal(para, threshold):
        return [orig.ExternalMatch(
            source="internal", similarity=0.88, title="Internal hit",
            citekey="smith2024", excerpt=para[:80],
        )]

    def fake_openalex(para, threshold):
        return [orig.ExternalMatch(
            source="openalex", similarity=0.81, title="OpenAlex hit",
            doi="10.1/x", excerpt=para[:80],
        )]

    monkeypatch.setattr(orig, "_internal_matches", fake_internal)
    monkeypatch.setattr(orig, "_external_matches_openalex", fake_openalex)
    monkeypatch.setattr(orig, "_external_matches_crossref", lambda p, t: [])

    report = orig.check_originality(
        str(draft),
        sources=("internal", "openalex", "crossref"),
        internal_threshold=0.85,
        external_threshold=0.80,
        min_chars=50,
    )

    assert len(report.paragraphs) == 2
    for p in report.paragraphs:
        sources_in_matches = {m.source for m in p.matches}
        assert sources_in_matches == {"internal", "openalex"}
    assert report.summary == "0 red flag(s), 2 yellow flag(s)"


@pytest.mark.unit
def test_check_originality_skips_short_paragraphs(tmp_path, monkeypatch):
    from research_assistant.verification import originality as orig

    draft = tmp_path / "draft.md"
    draft.write_text("tiny\n\n" + "long enough paragraph " * 20, encoding="utf-8")

    monkeypatch.setattr(orig, "_internal_matches", lambda p, t: [])
    monkeypatch.setattr(orig, "_external_matches_openalex", lambda p, t: [])
    monkeypatch.setattr(orig, "_external_matches_crossref", lambda p, t: [])

    report = orig.check_originality(str(draft), min_chars=50)
    assert len(report.paragraphs) == 0   # short paragraph filtered, long one has no matches → not flagged
```

- [ ] **Step 2: Run, fail**

Run: `python3 -m pytest tests/verification/test_originality.py -v`

Expected: FAIL — `check_originality` not implemented yet.

- [ ] **Step 3: Implement the orchestrator**

Append to `research_assistant/verification/originality.py`:

```python
from research_assistant.common import read_file
from research_assistant.researcher import (
    CHROMA_DIR,
    DEFAULT_EMBED_MODEL,
    _embed_single,
    _get_collection,
)
from research_assistant.verification.paraphrase_check import split_paragraphs
from research_assistant.verification import external_match as _em

DEFAULT_INTERNAL_THRESHOLD = 0.85
DEFAULT_EXTERNAL_THRESHOLD = 0.80
DEFAULT_MIN_CHARS = 150
DEFAULT_SOURCES: tuple[str, ...] = ("internal", "openalex", "crossref")
EXTERNAL_FETCH_LIMIT = 5


def _internal_matches(paragraph: str, threshold: float) -> list[ExternalMatch]:
    """Cosine-similarity matches against the local Chroma index (your indexed library)."""
    if not CHROMA_DIR.exists():
        return []
    collection = _get_collection()
    emb = _embed_single(paragraph, model=DEFAULT_EMBED_MODEL)
    results = collection.query(
        query_embeddings=[emb],
        n_results=5,
        include=["documents", "metadatas", "distances"],
    )
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    out: list[ExternalMatch] = []
    for doc, meta, dist in zip(docs, metas, dists, strict=False):
        if doc is None or meta is None or dist is None:
            continue
        sim = 1.0 - dist
        if sim < threshold:
            continue
        out.append(
            ExternalMatch(
                source="internal",
                similarity=round(sim, 4),
                title=meta.get("title", "") or "",
                authors=meta.get("authors_short") or None,
                year=int(meta["year"]) if (meta.get("year") or "").isdigit() else None,
                doi=meta.get("doi") or None,
                citekey=meta.get("citekey") or None,
                excerpt=doc[:300],
            )
        )
    return out


def _external_matches_from(source: str, paragraph: str, threshold: float) -> list[ExternalMatch]:
    """Shared OpenAlex/Crossref helper. Cosine sim is computed from abstracts."""
    candidates = _em.cached_search(source, paragraph, limit=EXTERNAL_FETCH_LIMIT)
    if not candidates:
        return []

    para_emb = _embed_single(paragraph, model=DEFAULT_EMBED_MODEL)
    out: list[ExternalMatch] = []
    for cand in candidates:
        abstract = (cand.get("abstract") or "").strip()
        if not abstract:
            continue
        cand_emb = _embed_single(abstract, model=DEFAULT_EMBED_MODEL)
        sim = _cosine(para_emb, cand_emb)
        if sim < threshold:
            continue
        out.append(
            ExternalMatch(
                source=source,                         # type: ignore[arg-type]
                similarity=round(sim, 4),
                title=cand.get("title", "") or "",
                authors=cand.get("authors"),
                year=cand.get("year"),
                doi=cand.get("doi"),
                excerpt=abstract[:300],
                url=cand.get("url"),
            )
        )
    return out


def _external_matches_openalex(paragraph: str, threshold: float) -> list[ExternalMatch]:
    return _external_matches_from("openalex", paragraph, threshold)


def _external_matches_crossref(paragraph: str, threshold: float) -> list[ExternalMatch]:
    return _external_matches_from("crossref", paragraph, threshold)


def _cosine(a: list[float], b: list[float]) -> float:
    import math
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def check_originality(
    draft_path: str,
    *,
    sources: tuple[str, ...] = DEFAULT_SOURCES,
    internal_threshold: float = DEFAULT_INTERNAL_THRESHOLD,
    external_threshold: float = DEFAULT_EXTERNAL_THRESHOLD,
    min_chars: int = DEFAULT_MIN_CHARS,
) -> OriginalityReport:
    """Run all configured sources against every substantive paragraph in the draft."""
    text = read_file(draft_path)
    paragraphs = [p for p in split_paragraphs(text) if len(p) >= min_chars]

    report_paragraphs: list[ParagraphReport] = []
    for i, para in enumerate(paragraphs):
        matches: list[ExternalMatch] = []
        if "internal" in sources:
            matches += _internal_matches(para, internal_threshold)
        if "openalex" in sources:
            matches += _external_matches_openalex(para, external_threshold)
        if "crossref" in sources:
            matches += _external_matches_crossref(para, external_threshold)
        if matches:
            report_paragraphs.append(ParagraphReport(index=i, text=para, matches=matches))

    return OriginalityReport(paragraphs=report_paragraphs)
```

- [ ] **Step 4: Run, pass**

Run: `python3 -m pytest tests/verification/test_originality.py -v`

Expected: 4 PASS (schema + summary + orchestrator + skip-short).

- [ ] **Step 5: Run the full suite**

Run: `python3 -m pytest -q`

Expected: 117 passed.

- [ ] **Step 6: Commit**

```bash
git add research_assistant/verification/originality.py tests/verification/test_originality.py
git commit -m "feat(verification): implement check_originality orchestrator"
```

---

## Task 14: Add the Click CLI (`ra-originality`)

**Files:**
- Modify: `research_assistant/verification/originality.py`
- Create: `tests/test_originality_cli.py`

- [ ] **Step 1: Write the failing CLI test**

```python
# tests/test_originality_cli.py
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
```

- [ ] **Step 2: Run, fail**

Run: `python3 -m pytest tests/test_originality_cli.py -v`

Expected: FAIL — `originality.main` doesn't exist.

- [ ] **Step 3: Add the Click command at the bottom of `originality.py`**

Append:

```python
import json as _json
import sys

import click
from rich.console import Console
from rich.table import Table

_console = Console()


@click.command()
@click.argument("draft_file")
@click.option("--sources", default=",".join(DEFAULT_SOURCES),
              help="Comma-separated subset of: internal,openalex,crossref.")
@click.option("--internal-threshold", default=DEFAULT_INTERNAL_THRESHOLD, type=float,
              help="Min cosine similarity vs. your indexed library to flag (0-1).")
@click.option("--external-threshold", default=DEFAULT_EXTERNAL_THRESHOLD, type=float,
              help="Min cosine similarity vs. OpenAlex/Crossref abstracts (0-1).")
@click.option("--min-chars", default=DEFAULT_MIN_CHARS, type=int,
              help="Skip paragraphs shorter than this many characters.")
@click.option("--json", "as_json", is_flag=True,
              help="Output the OriginalityReport as JSON.")
def main(draft_file, sources, internal_threshold, external_threshold, min_chars, as_json):
    """Flag paragraphs that look too similar to indexed papers or to published abstracts."""
    src_tuple = tuple(s.strip() for s in sources.split(",") if s.strip())
    valid = {"internal", "openalex", "crossref"}
    invalid = set(src_tuple) - valid
    if invalid:
        click.echo(f"Unknown source(s): {sorted(invalid)}. Valid: {sorted(valid)}.", err=True)
        sys.exit(2)

    report = check_originality(
        draft_file,
        sources=src_tuple,
        internal_threshold=internal_threshold,
        external_threshold=external_threshold,
        min_chars=min_chars,
    )

    if as_json:
        click.echo(_json.dumps(report.model_dump(), indent=2, ensure_ascii=False))
        if any(p.severity == "red" for p in report.paragraphs):
            sys.exit(1)
        return

    _console.print(f"\n[bold]Originality check: {draft_file}[/bold]")
    _console.print(f"[dim]{report.summary}[/dim]\n")

    if not report.paragraphs:
        _console.print("[green]✓ No paragraphs exceeded similarity thresholds.[/green]")
        return

    table = Table(title="Flagged paragraphs", show_lines=True)
    table.add_column("#", style="cyan", width=4)
    table.add_column("Severity", style="bold", width=8)
    table.add_column("Top match", style="white", width=44)
    table.add_column("Sim", style="red", width=6)
    table.add_column("Excerpt", style="dim", width=44)

    severity_style = {"red": "red", "yellow": "yellow", "green": "green"}
    for p in report.paragraphs:
        top = max(p.matches, key=lambda m: m.similarity)
        cite = f"@{top.citekey}" if top.citekey else (top.doi or top.url or "(no id)")
        label = f"[{top.source}] {cite} — {top.title[:30]}"
        excerpt = p.text[:120].replace("\n", " ")
        if len(p.text) > 120:
            excerpt += "…"
        sev = p.severity
        table.add_row(
            str(p.index),
            f"[{severity_style[sev]}]{sev.upper()}[/{severity_style[sev]}]",
            label,
            f"{top.similarity:.2f}",
            excerpt,
        )
    _console.print(table)

    if any(p.severity == "red" for p in report.paragraphs):
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run CLI tests**

Run: `python3 -m pytest tests/test_originality_cli.py -v`

Expected: 2 PASS.

- [ ] **Step 5: Run the whole suite**

Run: `python3 -m pytest -q`

Expected: 119 passed.

- [ ] **Step 6: Commit**

```bash
git add research_assistant/verification/originality.py tests/test_originality_cli.py
git commit -m "feat(cli): add ra-originality Click command"
```

---

## Task 15: Wire `ra-originality` into pyproject.toml as a console script

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the entry point**

In `pyproject.toml` `[project.scripts]`, add a new line beside the other `ra-*` entries:

```toml
ra-originality = "research_assistant.verification.originality:main"
```

- [ ] **Step 2: Reinstall the package so the new script is on PATH**

Run: `pip install -e . --quiet`

Expected: completes without error.

- [ ] **Step 3: Smoke-test the installed CLI**

Run: `ra-originality --help`

Expected: usage output listing the flags from Task 14.

- [ ] **Step 4: Lint**

Run: `python3 -m ruff check research_assistant/verification/ tests/`

Expected: All checks passed.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "chore: register ra-originality console script"
```

---

## Task 16: Expose Originality check in the web UI

**Files:**
- Modify: `research_assistant/web/tool_runner.py` — add the `ToolSpec` and module mapping

- [ ] **Step 1: Write the failing test that the tool is in TOOL_SPECS and reachable in the UI**

Append to `tests/web/test_tools_template.py`:

```python
@pytest.mark.unit
def test_originality_tool_is_registered(client):
    from research_assistant.web.tool_runner import TOOL_SPECS, _MODULE_BY_NAME

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
```

- [ ] **Step 2: Run, fail**

Run: `python3 -m pytest tests/web/test_tools_template.py::test_originality_tool_is_registered -v`

Expected: FAIL — `originality` not in TOOL_SPECS.

- [ ] **Step 3: Add the `ToolSpec` entry**

In `research_assistant/web/tool_runner.py`, **inside the `TOOL_SPECS` tuple**, in the `# ── Audit & verify` block, append a new entry (after `claim_verify`):

```python
    ToolSpec(
        name="originality",
        label="Originality check",
        category="audit",
        description=(
            "Flag paragraphs that look too similar to (a) your own indexed library "
            "or (b) published abstracts on OpenAlex / Crossref. Not a true plagiarism "
            "detector — it produces leads for human review."
        ),
        fields=(
            Field("draft_file", "Draft", "file_or_text", required=True, rows=14,
                  help="Paste the chapter / section text, or supply a path under THESIS_ROOT."),
            Field("sources", "Sources to check", "text", flag="--sources",
                  default="internal,openalex,crossref",
                  help=("Comma-separated subset of internal, openalex, crossref. "
                        "Internal checks your indexed Zotero papers; the other two query "
                        "published academic abstracts.")),
            Field("internal_threshold", "Internal similarity threshold", "number",
                  flag="--internal-threshold", default=0.85, min=0.5, max=1.0, step=0.01,
                  help="Higher = stricter. 0.85 catches near-verbatim; 0.75 catches close paraphrase."),
            Field("external_threshold", "External similarity threshold", "number",
                  flag="--external-threshold", default=0.80, min=0.5, max=1.0, step=0.01,
                  help="Cosine similarity between your paragraph and the matched abstract."),
            Field("min_chars", "Skip paragraphs shorter than", "number", flag="--min-chars",
                  default=150, min=10, max=500, step=10,
                  help="Tiny paragraphs are too noisy to check reliably."),
            Field("as_json", "JSON output", "checkbox", flag="--json",
                  help="Output as JSON instead of the rendered table."),
        ),
        long_running=True,
    ),
```

And in the `_MODULE_BY_NAME` dict near the bottom, in the verification subpackage block, add:

```python
    "originality":      "research_assistant.verification.originality",
```

- [ ] **Step 4: Run UI registration test**

Run: `python3 -m pytest tests/web/test_tools_template.py::test_originality_tool_is_registered -v`

Expected: PASS.

- [ ] **Step 5: Run the Field-help coverage test (the new fields all have help, so it should still pass)**

Run: `python3 -m pytest tests/web/test_field_help_coverage.py -v`

Expected: PASS.

- [ ] **Step 6: Run full suite**

Run: `python3 -m pytest -q`

Expected: 120 passed.

- [ ] **Step 7: Lint**

Run: `python3 -m ruff check research_assistant/ tests/`

Expected: All checks passed.

- [ ] **Step 8: Manual sanity check in the dev UI**

```bash
python3 -m research_assistant.web.app &
sleep 1
curl -s http://127.0.0.1:5050/tools/originality | grep -c "Originality check"
kill %1
```

Expected: at least 1.

- [ ] **Step 9: Commit**

```bash
git add research_assistant/web/tool_runner.py tests/web/test_tools_template.py
git commit -m "feat(ui): expose ra-originality via /tools/originality"
```

---

## Task 17: Update the README to document the new tool

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Find where existing `ra-*` commands are documented**

Run: `grep -n "ra-claim-verify\|ra-audit\|ra-verify" README.md | head`

Use the line numbers to locate the existing table or list of audit/verification scripts.

- [ ] **Step 2: Add a row for `ra-originality`**

In the same table or list, insert (matching surrounding markdown style):

```markdown
| `ra-originality`   | Originality check (internal + OpenAlex / Crossref)      |
```

If the README uses a bulleted list instead of a table, mirror that style.

- [ ] **Step 3: Append a usage section near other audit-tool usage examples**

Find an existing usage block (e.g., search for `ra-paraphrase-check\|ra-claim-verify`) and place a new block immediately after:

````markdown
### Originality / plagiarism check

```bash
# Default: all three sources, sensible thresholds
ra-originality drafts/ch1.md

# Internal-only (faster, no network)
ra-originality drafts/ch1.md --sources internal

# Stricter thresholds
ra-originality drafts/ch1.md --internal-threshold 0.80 --external-threshold 0.75 --json
```

Not a true plagiarism detector — it flags paragraphs that look too close to your
own indexed library or to published academic abstracts (via OpenAlex and Crossref).
Results require human review.

Set `OPENALEX_EMAIL=you@example.com` in `.env` to use OpenAlex's polite request pool.
````

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document ra-originality command in README"
```

---

## Task 18: Final sweep — lint, test, summary

- [ ] **Step 1: Full lint**

Run: `python3 -m ruff check research_assistant/ tests/`

Expected: All checks passed.

- [ ] **Step 2: Full test suite**

Run: `python3 -m pytest -v`

Expected: 120 passed (or more if intermediate task tests landed). Zero failures.

- [ ] **Step 3: Confirm git log**

Run: `git log --oneline -20`

Expected: ~17 commits, one per task, all on the current branch, all with descriptive messages.

- [ ] **Step 4: (Optional) Push or open a PR**

If you have a remote configured:

```bash
git push -u origin HEAD
gh pr create --title "Plan A: UX clarity + Originality check" \
             --body "Implements docs/superpowers/plans/2026-05-24-plan-a-ux-clarity-and-originality.md"
```

---

# Follow-up plans (not in this document)

Once Plan A is merged, the next sub-projects from the parent spec are:

- **Plan B — Agent foundation + CLI refactor** (spec §1-5, §11 risks). LangGraph wiring, CLIChatModel adapter, structured outputs, port pipeline.py's stages to nodes, add iteration loop / tool-using writer behind feature flags.
- **Plan C — Workbench UI + Runs + error overlay** (spec §6, §6.5 partial, §7). The new `/workbench` page with SSE streaming, `/runs` history, global error overlay component, dual JSONL+SQLite storage.
- **Plan D — Supporting UI** (spec §6.5 remainder). `/usage`, `/settings` with provider-ping, `/logs` viewer, `/files` browser with inline editor, `/files/bib`.

Each follow-up plan should be written using `superpowers:writing-plans` against the same source spec, after Plan A ships and we learn what to revise.
