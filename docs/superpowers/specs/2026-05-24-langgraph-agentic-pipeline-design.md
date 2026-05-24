# LangGraph Agentic Pipeline + Unified Web Workbench — Design

**Date:** 2026-05-24
**Status:** Approved (revised after UI-completeness audit)
**Author:** Brainstorming session with `superpowers:brainstorming`
**Revision:** R3 — adds Section 12 (UX clarity: descriptions and per-field help text everywhere) and Section 13 (Originality check tool: internal + OpenAlex/Crossref). R2 added: CLIChatModel adapter, /logs viewer, /files browser + editor, /bib viewer, /settings provider-ping, global error overlay.

## 1. Problem & Goal

`research-assistant` today is a strong **RAG + linear pipeline** system:

- ~15 CLI tools (`ra-ideas`, `ra-outline`, `ra-critique`, `ra-verify`, …) each independent.
- `pipeline.py` is a fixed 5-step chain (retrieve → writer → paraphraser → critic → verify) with prompts baked inline, no retries, no shared state, no iteration. Critic's `REJECT` verdict is logged and ignored.
- Web UI is a dashboard + a generic `/tools/<name>` Click-runner — a *bag of tools*, not a workbench.

Goal: push the system from the **RAG / early-AI-Agent** tier toward the **Agentic-AI / Coordinator** tier, with a first-class web UI that makes the orchestration visible and usable.

In scope for this design: Phase 1 (agent foundation) + Phase 2 (iteration loops, tool-using writer) + full unified web UI (Workbench, Runs, Usage, Settings).

Out of scope (Phase 3, future): top-level planner-agent that decides which capabilities to call for an open-ended task. The architecture leaves room for it; we will not build it now.

## 2. Architecture Overview

A new `research_assistant/agents/` subpackage owns all LangGraph-based orchestration. Existing CLI tools and the per-tool `/tools/<name>` page keep working untouched. `pipeline.py` shrinks to a thin compatibility wrapper that builds the graph and runs it.

```
research_assistant/
├── agents/                        ← NEW
│   ├── __init__.py                ← exports: build_writing_graph, run_writing_pipeline, RunState
│   ├── state.py                   ← TypedDict RunState
│   ├── schemas.py                 ← Pydantic: Critique, Issue, RetrievalReport, VerifierReport, StepRecord
│   ├── models.py                  ← Factory: routes to ChatLiteLLM (API) or CLIChatModel (subprocess) based on MODELS value
│   ├── cli_chat_model.py          ← NEW: LangChain BaseChatModel subclass wrapping common._ask_via_cli — keeps the 4 CLI aliases (claude-cli/gemini-cli/codex-cli/ollama-cli) working in the graph
│   ├── policies.py                ← PipelineConfig + iteration knobs
│   ├── observability.py           ← @traced decorator, JSONL writer, SSE event bus
│   ├── nodes/
│   │   ├── retriever.py
│   │   ├── discover.py            ← graph node when auto_discover_on_thin fires; wraps research/discover.py
│   │   ├── writer.py              ← tool-using
│   │   ├── paraphraser.py
│   │   ├── critic.py              ← structured Critique output
│   │   └── verifier.py            ← deterministic citekey check, no LLM
│   ├── tools/                     ← LangChain Tools the writer can call mid-draft
│   │   ├── rag_retrieve.py        ← shares impl with nodes/retriever.py
│   │   ├── discover.py            ← shares impl with nodes/discover.py
│   │   └── zot_search.py          ← wraps research/zot.py
│   └── graphs/
│       └── writing_pipeline.py    ← StateGraph wiring + conditional edges
├── pipeline.py                    ← REFACTORED: ~80 lines; CLI front door, calls agents.run_writing_pipeline
└── web/
    ├── app.py                     ← + routes: /workbench, /workbench/run, /workbench/stream/<id>, /runs, /runs/<id>, /usage, /settings, /logs, /files, /files/bib
    ├── workbench.py               ← NEW: SSE bridge between graph and HTTP
    ├── runs_store.py              ← NEW: JSONL writer + SQLite index (dual storage)
    ├── usage_store.py             ← NEW: aggregations over ~/thesis/logs/*.jsonl
    ├── settings_store.py          ← NEW: user prefs + provider-ping health check
    ├── logs_view.py               ← NEW: paginated/filtered reader for ~/thesis/logs/*.jsonl
    ├── files_browser.py           ← NEW: read THESIS_ROOT tree, safe-path resolution, file ops
    ├── bib_view.py                ← NEW: parse bib/thesis.bib + cross-reference with latest run citations
    ├── errors.py                  ← NEW: ErrorReport dataclass + helpers for the global error overlay
    ├── templates/
    │   ├── base.html              ← + nav links + dark theme toggle + global error overlay partial
    │   ├── _error_overlay.html    ← NEW (Jinja partial included on every page)
    │   ├── workbench.html         ← NEW
    │   ├── workbench_event.html   ← NEW (HTMX SSE fragment per node event)
    │   ├── runs.html              ← NEW
    │   ├── run_detail.html        ← NEW
    │   ├── usage.html             ← NEW
    │   ├── logs.html              ← NEW
    │   ├── files.html             ← NEW (tree + file actions)
    │   ├── file_detail.html       ← NEW (read + inline CodeMirror editor)
    │   ├── bib.html               ← NEW
    │   └── settings.html          ← NEW
    └── static/
        ├── style.css              ← + dark-mode workbench styles + error-overlay styles
        ├── workbench.js           ← ~50 lines: SSE event handling, graph state updates
        ├── editor.js              ← ~30 lines: CodeMirror init from CDN, save button hook
        └── error_overlay.js       ← ~20 lines: slide-in panel, copy-as-bug-report
```

### Boundary rules

1. **`agents/` is self-contained.** Nothing in `research/`, `writing/`, `verification/` imports from `agents/`. The dependency arrow points *into* `agents/` only.
2. **Nodes wrap existing capability code, don't replace it.** `nodes/retriever.py` calls `researcher.retrieve_chunks`; `nodes/verifier.py` calls `verification.verify`. No rewriting of capability code in this work.
3. **Tools vs nodes is deliberate.** A *node* is a graph stage. A *tool* is something a node can invoke ad-hoc (writer requesting more retrieval mid-draft). Initial retrieval is a node; mid-draft retrieval is a tool call.
4. **`pipeline.py` stays the CLI entry point** so `ra-pipeline` keeps working.

### New dependencies (pinned)

- `langgraph>=0.2,<0.3`
- `langchain-core>=0.3,<0.4`
- `langchain-litellm>=0.1` — preserves the existing `MODELS` registry and litellm cost logging
- `tenacity>=8.0` — retry policy for LLM calls
- `pydantic>=2.0` — already implied by langchain ecosystem (2.12 already installed)
- `bibtexparser>=2.0` — for `/files/bib` viewer (pure Python, no compile)

No new runtime dep for SQLite (stdlib `sqlite3`) or CodeMirror (loaded from CDN at runtime).

## 3. RunState & Structured Outputs

### `agents/state.py`

```python
from typing import TypedDict, Annotated
from operator import add
from research_assistant.agents.schemas import (
    RetrievalReport, Critique, VerifierReport, StepRecord
)
from research_assistant.agents.policies import PipelineConfig

class RunState(TypedDict):
    # Inputs — set once, never modified
    run_id: str
    question: str
    config: PipelineConfig

    # Mutable working state — overwritten each iteration
    retrieval: RetrievalReport | None
    draft: str | None
    paraphrased: str | None
    critique: Critique | None
    verifier: VerifierReport | None

    # Loop control
    iteration: int              # 0-indexed; ++ when re-entering writer
    cost_so_far: float

    # Observability — appended via LangGraph reducer
    history: Annotated[list[StepRecord], add]
```

### `agents/schemas.py` (Pydantic)

```python
class Issue(BaseModel):
    category: Literal["clarity", "support", "citation", "overreach", "structure"]
    severity: Literal["low", "med", "high"]
    quoted_text: str | None
    suggestion: str

class Critique(BaseModel):
    issues: list[Issue]
    verdict: Literal["ACCEPT", "REVISE", "REJECT"]
    summary: str
    @property
    def needs_revision(self) -> bool: return self.verdict != "ACCEPT"

class Chunk(BaseModel):
    source: str          # file path or citekey
    text: str
    score: float

class RetrievalReport(BaseModel):
    chunks: list[Chunk]
    context_block: str
    is_thin: bool        # len(chunks) < min OR mean(scores) < threshold
    sources_count: int

class VerifierReport(BaseModel):
    total_citations: int
    resolved: list[str]
    missing: list[str]
    bib_path: str | None
    skipped_reason: str | None

class StepRecord(BaseModel):
    node: str
    model: str | None
    started_at: datetime
    duration_ms: int
    input_tokens: int | None
    output_tokens: int | None
    cost: float | None
    summary: str         # short human-readable line for the UI stream
```

The critic node uses `chat_model.with_structured_output(Critique)` so we never parse free-text. The verifier node is deterministic (citekey set intersection against the `.bib` file) and constructs `VerifierReport` directly — no LLM involved.

### `agents/policies.py`

```python
@dataclass(frozen=True)
class PipelineConfig:
    writer_model: str
    paraphraser_model: str
    critic_model: str
    iterate: bool = True
    max_iters: int = 3
    cost_cap_usd: float = 5.0
    allow_tools: bool = True            # writer can call rag_retrieve, discover, zot_search
    auto_discover_on_thin: bool = False # if retrieval is thin, auto-call discover
    thin_chunks_min: int = 5
    thin_score_min: float = 0.45
    verify_bib_path: str | None = "bib/thesis.bib"
    temperature_writer: float = 0.3
    temperature_paraphraser: float = 0.3
    temperature_critic: float = 0.2
```

## 4. Graph Wiring & Conditional Edges

```
                      ┌─────────────┐
                      │  retriever  │
                      └──────┬──────┘
                             │
                ┌────────────▼─────────────┐
                │ is_thin AND auto_disc?   │
                └──────┬──────────┬────────┘
                  yes  │          │ no
                       ▼          │
                ┌─────────────┐   │
                │  discover   │   │
                └──────┬──────┘   │
                       │          │
                       └────►◄────┘
                             │
                      ┌──────▼──────┐
                      │   writer    │◄────────────┐
                      └──────┬──────┘             │
                       (may call tools:           │
                        rag_retrieve, discover)   │
                             │                    │
                      ┌──────▼──────┐             │
                      │ paraphraser │             │
                      └──────┬──────┘             │
                             │                    │
                      ┌──────▼──────┐             │
                      │   critic    │             │
                      └──────┬──────┘             │
                             │                    │
              ┌──────────────▼──────────────┐     │
              │ ACCEPT? OR iter >= max?     │     │
              │ OR cost >= cap?             │     │
              └──────┬────────────┬─────────┘     │
                 yes │            │ no            │
                     ▼            └───────────────┘
              ┌─────────────┐    (writer re-enters with critique in state)
              │  verifier   │
              └──────┬──────┘
                     ▼
                    END
```

### Conditional edge functions (pure, on `RunState`)

```python
def after_retriever(state: RunState) -> Literal["discover", "writer"]:
    if state["config"].auto_discover_on_thin and state["retrieval"].is_thin:
        return "discover"
    return "writer"

def after_critic(state: RunState) -> Literal["verifier", "writer"]:
    cfg = state["config"]
    if not cfg.iterate:
        return "verifier"
    if state["critique"].verdict == "ACCEPT":
        return "verifier"
    if state["iteration"] + 1 >= cfg.max_iters:
        return "verifier"
    if state["cost_so_far"] >= cfg.cost_cap_usd:
        return "verifier"
    return "writer"   # writer increments iteration; sees critique in state
```

### Tool-using writer

```python
# nodes/writer.py
tools = [rag_retrieve, discover, zot_search] if state["config"].allow_tools else []
model = get_chat_model(state["config"].writer_model).bind_tools(tools)
# Standard LangGraph tool-calling loop until model returns final answer
```

## 5. Models, Observability, Error Handling

### Models — one source of truth

`agents/models.py`:

```python
from langchain_litellm import ChatLiteLLM
from research_assistant.common import MODELS

def get_chat_model(role_alias: str, *, temperature: float = 0.3) -> BaseChatModel:
    """role_alias is a key in MODELS dict ('claude', 'gemini', 'gpt', etc.)."""
    return ChatLiteLLM(model=MODELS[role_alias], temperature=temperature)
```

This preserves the existing model registry and the per-call cost logging in `common.py`. No fragmentation.

### `agents/cli_chat_model.py` — covering the CLI-providers gap

The `MODELS` dict contains 4 aliases whose values start with `cli:` (`claude-cli`, `gemini-cli`, `codex-cli`, `ollama-cli`). These shell out to a subprocess instead of calling an API, so `ChatLiteLLM` cannot drive them. Without an adapter they would silently disappear from Workbench dropdowns.

`CLIChatModel` is a `langchain_core.language_models.BaseChatModel` subclass that:

1. Reads the `cli:<command>` template from `MODELS[alias]`.
2. Joins LangChain `BaseMessage` list into the same `[System]/[User]` block format `common._ask_via_cli` already produces.
3. Calls `subprocess.run(...)` with the same timeout/error semantics.
4. Returns a `ChatResult` with the stdout text. Token counts are `None`; cost is `$0.0` (subscription billing happens elsewhere — matches current behavior).
5. Reuses the JSONL logging in `common._log` so disclosure logs stay one source of truth.

`agents/models.py::get_chat_model(alias)` inspects `MODELS[alias]`: if it starts with `cli:`, return `CLIChatModel`; otherwise return `ChatLiteLLM`. All 14 aliases work identically inside graph nodes and tool-using writer flows. Structured-output calls (`with_structured_output(Critique)`) on a CLI model fall back to a JSON-coerce retry since CLIs don't expose function-calling — if both attempts fail, the critic node returns a `Critique(verdict="REVISE", issues=[], summary="cli model unable to produce structured output")` and the graph continues.

### Observability

```python
# agents/observability.py
def traced(node_name: str):
    def deco(node_fn):
        def wrapped(state: RunState) -> dict:
            t0 = time.monotonic()
            started = datetime.now(UTC)
            try:
                result = node_fn(state)
            except Exception as e:
                _emit_error(state["run_id"], node_name, e)
                raise
            duration_ms = int((time.monotonic() - t0) * 1000)
            record = StepRecord(node=node_name, ..., duration_ms=duration_ms, ...)
            _write_jsonl(state["run_id"], record)
            _emit_sse(state["run_id"], record)
            result.setdefault("history", []).append(record)
            return result
        return wrapped
    return deco
```

Per-run JSONL file at `~/thesis/runs/<run_id>.jsonl` is append-only and the source of truth.

### Error handling

- **LLM API errors** — 3 retries with exponential backoff via `tenacity`.
- **Structured-output validation failures** — 1 reformat retry; then fail-fast with a `StepRecord(node=..., summary="schema validation failed: ...")` and short-circuit to `verifier` with `verifier.skipped_reason="upstream failure"`.
- **Cost cap exceeded** — `after_critic` short-circuits to `verifier`; run marked `cost_capped` in SQLite index.
- **Empty retrieval** — same as today: pipeline aborts after `retriever` with a clear error in the trace.

## 6. Unified Web UI

Stack stays Flask + HTMX + Tailwind. Server-Sent Events for streaming (HTMX `hx-ext="sse"`). Total new JS under 50 lines (just SSE event handling).

### MVP routes

| Route | Method | Purpose |
|---|---|---|
| `/workbench` | GET | The new front-door page |
| `/workbench/run` | POST | Create run, return SSE channel URL |
| `/workbench/stream/<run_id>` | GET (SSE) | Live event stream from the graph |
| `/runs` | GET | List of all runs (paginated, filterable) |
| `/runs/<run_id>` | GET | Full trace inspector |
| `/runs/<run_id>/fork` | POST | Clone settings, open in workbench |
| `/usage` | GET | Cost dashboard from `~/thesis/logs/*.jsonl` |
| `/settings` | GET/POST | Model presets, default iteration knobs, API key health |
| `/settings/ping` | POST | Pings every configured provider with a tiny call, returns per-provider OK/fail with actual error message |
| `/logs` | GET | Paginated/filterable view of `~/thesis/logs/*.jsonl` (by date / model / status / search). Source of truth for "what did the model actually do" debugging. |
| `/logs/<date>/<n>` | GET | Single call detail: full prompt, full response, system message, tokens, cost. JSON or rendered. |
| `/files` | GET | Read-only browser of THESIS_ROOT. Sidebar tree (outputs/, outlines/, evidence/, bib/, runs/, sessions/). Click a file → detail. |
| `/files/view/<path>` | GET | File viewer with syntax highlighting + "Open in editor" + "Use as draft in Workbench" actions. Path-traversal protected against THESIS_ROOT. |
| `/files/edit/<path>` | GET | Same path opened in CodeMirror (CDN, single script). |
| `/files/save/<path>` | POST | Save edited content. Returns updated file detail. |
| `/files/bib` | GET | Special viewer for `bib/thesis.bib`: parsed entries table + which are used / unused in the latest run (cross-referenced via `VerifierReport.resolved`). |
| `/errors/report` | POST | Endpoint the global error overlay POSTs to when user clicks "copy as bug report" — returns a sanitized text blob (argv, exit code, stderr tail, env summary minus secrets). |

### `/workbench` layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Workbench                                                  [Settings ⚙] │
├──────────────────────────┬───────────────────────────────────────────────┤
│  WHAT DO YOU WANT?       │  LIVE RUN                            ● running│
│  ┌────────────────────┐  │  ┌──────────────────────────────────────────┐ │
│  │ <question>         │  │  │ ✓ retriever     gemini-flash    1.2s    │ │
│  └────────────────────┘  │  │   18 chunks · score 0.72 avg            │ │
│                          │  ├──────────────────────────────────────────┤ │
│  ROLES                   │  │ ✓ writer        claude-opus-4.7  8.4s   │ │
│  Writer    [claude  ▾]   │  │   238 words · 6 citations               │ │
│  Paraphr.  [gemini  ▾]   │  │   [show draft ▾]                        │ │
│  Critic    [gpt-5   ▾]   │  ├──────────────────────────────────────────┤ │
│                          │  │ ⏳ critic       gpt-5          ...      │ │
│  ITERATION               │  └──────────────────────────────────────────┘ │
│  ☑ Iterate on REVISE     │                                               │
│  Max iters  [3 ▾]        │  GRAPH STATE                                  │
│  ☑ Allow mid-draft tools │  retrieve → write → paraphrase → critic      │
│  ☐ Auto-discover if thin │                          ↑       │           │
│                          │                          └──REVISE ──────────┘│
│  COST CAP  $ [2.00  ]    │  Iteration 1 of 3 · spent $0.47 / $2.00      │
│                          │                                               │
│  [ ▶ Run pipeline ]      │  [Stop] [Save run] [Export markdown]          │
└──────────────────────────┴───────────────────────────────────────────────┘
```

Form posts to `/workbench/run` → backend creates a `run_id`, starts the LangGraph in a background thread, returns SSE URL → HTMX subscribes to `/workbench/stream/<run_id>` → each `StepRecord` becomes an HTML fragment appended to the run panel.

### Visual style — dark-mode coding UI

- Monospace headings (JetBrains Mono / Cascadia), regular sans for body
- Dark base (`#0d1117` à la GitHub dark), subtle borders, syntax-highlighted prompts/outputs
- Run-node cards with status pill (pending/running/done/error) — running pill has a subtle pulse
- Theme toggle in nav (light/dark), defaults to dark
- Existing pages remain in light theme unless user toggles globally

### `/runs` and `/runs/<id>`

- `/runs` reads SQLite index for fast filter by date / model / cost / verdict.
- `/runs/<id>` reads the JSONL trace file as source of truth — full event timeline, every iteration's draft + critique side-by-side (diff view between iterations 1, 2, 3), every tool call.
- "Fork run" → POST `/runs/<id>/fork` returns to `/workbench` with form pre-filled.

### `/usage`

- Aggregations from existing `~/thesis/logs/*.jsonl`: spend per model per day, spend per tool, total spend over time, top-N most expensive runs.
- Simple charts via Chart.js (single CDN script) — no new pip dep.

### `/settings`

- Saved model role presets ("default", "cheap", "premium") — JSON in `~/.config/research-assistant/settings.json`
- Default iteration knobs (max_iters, cost_cap)
- API-key health: **"Ping all providers" button** → POST `/settings/ping` makes a 1-token call to each API model (and `--version` for each CLI provider). Per-provider result: ✅ OK / ❌ with the real error string. No secrets in the displayed output.
- Index status (last indexed, chunk count) — already available, just surfaced here
- Theme preference (light/dark)

## 6.5 UI Completeness Pages — Debug & File Control

Three additional pages and one global component close the "can I control and debug everything via UI" gap.

### `/logs` — JSONL call log viewer

Reads `~/thesis/logs/*.jsonl`. Every `ask_model` and `_ask_via_cli` call (from anywhere in the codebase — RAG, pipeline, tools, agents) is already logged here. The viewer surfaces them:

- Filter by date range, model alias, via=api|cli, has-error.
- Search across prompt + response text (substring match — full-text search is overkill for this scale).
- Each row shows: timestamp, model, tokens in/out, cost, first 80 chars of prompt.
- Click a row → `/logs/<date>/<n>` shows the full prompt, system, response side-by-side. "Replay in Workbench" sends the prompt to /workbench with same model preselected.
- This is the ground truth for any "why did the model say X?" debugging.

### `/files` — THESIS_ROOT browser

`THESIS_ROOT` (default `~/thesis/`) is where every tool saves output (`outlines/`, `evidence/`, `runs/`, `sessions/`, `bib/`, `chroma_db/`). Today users browse it in their file manager. The browser surfaces:

- Sidebar tree of top-level dirs under THESIS_ROOT, with file counts and last-modified.
- Click a dir → file list with size, modified, preview snippet.
- Click a file → `/files/view/<path>` renders content with syntax highlighting (markdown gets rendered, JSONL gets pretty-printed line-by-line, .bib gets parsed table view).
- Actions per file: **Open in editor** (loads CodeMirror), **Open in Workbench as draft** (POSTs to `/workbench` with file content as the `question` field's seed), **Download**.
- Path-traversal protected: every path is resolved and verified to start with `THESIS_ROOT.resolve()`; same pattern as `_safe_session_path` in current `app.py`.

### `/files/edit/<path>` — Inline editor

CodeMirror 6 loaded from CDN as a single `<script type="module">` tag — no build step, no npm. ~30 lines of JS in `editor.js`. Supports markdown and BibTeX modes. Save → POST `/files/save/<path>` → updated file detail rendered. After saving an outline or draft, an "Open in Workbench" button is one click away.

### `/files/bib` — Bibliography viewer

Special-case viewer for `bib/thesis.bib`:

- Parse entries via `bibtexparser>=2.0` (small dep, pure Python, no compile).
- Table: citekey, type, title, year, authors, **used in latest run?** (cross-referenced via `runs.db` → latest run's `VerifierReport.resolved` list).
- Filter: unused entries, entries from a date range.
- Edit single entry in modal (writes back via the same `/files/save` endpoint).

### Global error overlay (`_error_overlay.html`)

A single Jinja partial included by `base.html` and rendered on every page. JS in `error_overlay.js` listens for HTMX response events:

- If response status is 4xx/5xx OR response body contains a `<div data-error>...</div>` element, the overlay slides in from the right.
- Shows: short message, expandable details (argv, exit code, stderr tail, traceback if present).
- **Copy as bug report** button → POST `/errors/report` returns a redacted text blob (no API keys, no .env contents) the user can paste into a bug tracker.
- Dismiss = click outside or Esc.

Backend hook: every tool route and SSE event uses a small `errors.format_error(exc, *, argv, route)` helper to produce consistent error markup. Existing `/tools/*/run` adds the data-error attribute when `ToolResult.error` is set.

Result: every failure anywhere in the UI surfaces a structured, copyable, sanitized error — not a stderr tail in a `<pre>` block.

## 6.6 What "control everything via UI" means after this work

| Capability | Today | After this design |
|---|---|---|
| Run any of the 15 CLI tools | ✅ /tools/* | ✅ kept |
| Run full agentic pipeline live with streaming | ❌ | ✅ /workbench |
| Browse past runs, diff iterations, fork | ⚠️ sessions only | ✅ /runs |
| See per-provider cost/usage over time | ❌ | ✅ /usage |
| Edit API keys / model presets | ❌ | ✅ /settings |
| Verify each provider is reachable (ping-all) | ❌ | ✅ /settings/ping |
| View raw call logs (debug "what did the model say?") | ❌ | ✅ /logs |
| Replay any past call in Workbench | ❌ | ✅ /logs row action |
| Browse THESIS_ROOT outputs in UI | ❌ | ✅ /files |
| Edit a saved outline/draft in browser | ❌ | ✅ /files/edit/<path> |
| Use a saved file as Workbench seed | ❌ | ✅ /files action |
| View .bib entries + unused entries | ❌ | ✅ /files/bib |
| Get a copyable bug report when anything fails | ❌ | ✅ global error overlay |
| Use the 4 CLI-based model providers in agents | n/a | ✅ via CLIChatModel |

## 7. Storage — Dual JSONL + SQLite

### Source of truth: JSONL

`~/thesis/runs/<run_id>.jsonl` — one line per event. Schema:

```json
{"type": "run_start", "run_id": "...", "question": "...", "config": {...}, "ts": "..."}
{"type": "node_start", "node": "retriever", "ts": "..."}
{"type": "node_end", "node": "retriever", "duration_ms": 1234, "tokens_in": 0, "tokens_out": 0, "cost": 0.0, "summary": "18 chunks · 0.72 avg", "ts": "..."}
{"type": "tool_call", "node": "writer", "tool": "rag_retrieve", "args": {...}, "ts": "..."}
{"type": "iteration", "iteration": 1, "trigger": "critique_verdict_REVISE", "ts": "..."}
{"type": "run_end", "status": "completed", "iterations_used": 2, "total_cost": 0.47, "verdict": "ACCEPT", "ts": "..."}
```

### Derived index: SQLite

`~/thesis/runs/runs.db` — single `runs` table, rebuilt from JSONL via `ra-runs reindex`:

```sql
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    writer_model TEXT,
    paraphraser_model TEXT,
    critic_model TEXT,
    iterations_used INTEGER,
    max_iters INTEGER,
    total_cost REAL,
    verdict TEXT,
    status TEXT,            -- 'completed' | 'cost_capped' | 'error'
    duration_ms INTEGER,
    created_at TEXT NOT NULL,
    jsonl_path TEXT NOT NULL
);
CREATE INDEX idx_runs_created ON runs(created_at DESC);
CREATE INDEX idx_runs_status  ON runs(status);
```

`runs_store.py` writes both on `run_end`. If SQLite write fails, JSONL is unaffected — index can be rebuilt.

## 8. Backward Compatibility

### CLI

`ra-pipeline "question" --writer X --paraphraser Y --critic Z` keeps the same default output format. New flags are additive:

| Flag | Default | Effect |
|---|---|---|
| `--iterate / --no-iterate` | `--iterate` | Critic-driven revision loop |
| `--max-iters N` | 3 | Cap on revision iterations |
| `--cost-cap USD` | 5.0 | Short-circuit to verifier if exceeded |
| `--allow-tools / --no-tools` | `--allow-tools` | Writer can call rag_retrieve/discover/zot_search |
| `--auto-discover` | off | Call discover when retrieval is thin |
| `--legacy` | off | Forces single-pass, no tools, exact old behavior |

### Web UI

- Every existing page (`/`, `/ask`, `/compare`, `/sessions`, `/tools/*`) keeps working unchanged.
- New nav items: Workbench, Runs, Usage, Settings.
- `/tools/pipeline` adds a banner pointing users to `/workbench`.

### Library API

- Existing entry points in `research/`, `writing/`, `verification/`, `researcher.py` keep their signatures.
- `pipeline.py` keeps `run_pipeline()` and `format_report()` as public functions; their internals now build and run the graph.

## 9. Testing

| Layer | Test files | Approach |
|---|---|---|
| State & schemas | `tests/agents/test_state.py`, `test_schemas.py` | Pydantic validation, reducer behavior |
| Each node | `tests/agents/test_nodes/test_*.py` | `FakeChatModel` with canned structured outputs |
| Graph wiring | `tests/agents/test_graph.py` | Critic-loop terminates on ACCEPT and on max_iters; cost-cap short-circuits; thin-retrieval triggers discover; tool calls round-trip through state |
| Models | `tests/agents/test_models.py` | `get_chat_model` returns a callable; cost logging hook fires |
| Observability | `tests/agents/test_observability.py` | `@traced` writes JSONL + emits SSE event; errors are recorded |
| Workbench routes | `tests/web/test_workbench.py` | `/workbench/run` returns SSE URL; `/workbench/stream/<id>` emits at least one event |
| Runs store | `tests/web/test_runs_store.py` | JSONL written, SQLite indexed, reindex rebuilds DB from JSONL |
| Usage aggregation | `tests/web/test_usage_store.py` | Aggregation correct for synthetic JSONL |
| Settings | `tests/web/test_settings.py` | Read/write round-trip; API-key ping mocked |
| Provider ping | `tests/web/test_settings_ping.py` | Each provider class mocked; ping returns OK with valid creds, structured fail otherwise; no secret leakage in error string |
| Logs viewer | `tests/web/test_logs_view.py` | Paginate synthetic JSONL; filter by date/model/error; single-call detail renders escaped HTML |
| Files browser | `tests/web/test_files_browser.py` | Path-traversal blocked (`../`, absolute paths, symlinks outside THESIS_ROOT); tree listing; save round-trip |
| Bib viewer | `tests/web/test_bib_view.py` | Parse fixture .bib; cross-reference against synthetic `runs.db`; unused-entry filter correct |
| Error overlay | `tests/web/test_errors.py` | `format_error` redacts env vars matching `*_API_KEY` and `*_TOKEN`; bug-report blob has no secrets |
| CLIChatModel | `tests/agents/test_cli_chat_model.py` | subprocess mocked; message → CLI prompt formatting matches `_ask_via_cli`; timeout/failure paths covered; structured-output fallback returns valid REVISE critique |
| Legacy CLI | `tests/test_pipeline_legacy.py` | `ra-pipeline ... --legacy` produces output byte-identical to pre-refactor for canned inputs |

**Coverage target:** 80%+ on `agents/`, 70%+ on new `web/` code.

## 10. Build Sequence

1. **Foundation** — `agents/` package: state, schemas, policies, observability, **models.py + cli_chat_model.py**, all 5 nodes, graph wiring. Unit tests per node + graph + CLIChatModel.
1.5. **UX clarity quick-win** — `tools.html` renders `Field.help` for every field type; fill `help=` on every Field in TOOL_SPECS; dashboard tool catalog gets one-line descriptions; hand-written pages get inline `<details>` help blocks for technical params. Ships before the big UI work so all later pages inherit the pattern.
2. **CLI refactor** — `pipeline.py` becomes thin wrapper; add new flags; `--legacy` test passes.
2.5. **Originality check tool** — `verification/originality.py` + `external_match.py` + new TOOL_SPECS entry. Available via existing `/tools/originality` form immediately.
3. **Workbench UI + error overlay** — `/workbench` page + SSE bridge + `runs_store.py` (JSONL write). Global error overlay component shipped here so every later page benefits.
4. **Runs UI** — SQLite index + `/runs` list + `/runs/<id>` detail + fork.
5. **Usage + Settings (with provider-ping)** — dashboards + presets + `/settings/ping`.
6. **Logs viewer** — `/logs` paginated/filtered reader + single-call detail + "Replay in Workbench" action.
7. **Files browser + bib viewer** — `/files`, `/files/view`, `/files/edit` (CodeMirror), `/files/save`, `/files/bib`. Adds `bibtexparser>=2.0` dep.
8. **Test hardening + docs** — fill coverage gaps, update README, add screenshots.

Each step is independently shippable:
- After step 2 the CLI is already improved (all old flags still work).
- After step 3 the Workbench is usable for daily writing.
- After step 4 history works.
- After step 5 you can manage settings and see costs without touching .env.
- After step 6 you can debug "what did model X say last Tuesday" without leaving the browser.
- After step 7 you never need to leave the browser for thesis work.

Total expected delta: ~5500-6000 lines of code (incl. tests). Existing CLI tools and `/tools/*` page untouched.

## 11. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| LangGraph version churn | Pin `>=0.2,<0.3`. All graph wiring isolated in `graphs/writing_pipeline.py` (~150 lines) — re-pinning is a single-file change. |
| `langchain-litellm` cost-logging double-counts vs. existing `common.py` logger | One logging path only — disable litellm's internal callback, keep `common.py`'s. Asserted in tests. |
| Tool-using writer infinite loop | LangGraph already enforces a recursion limit per run; set to 10. Cost cap is the hard backstop. |
| SSE connection drops mid-run | Run continues server-side; client reconnects with `Last-Event-ID` and replays from JSONL. Standard SSE pattern. |
| SQLite write contention from concurrent runs | Single writer thread per process; web app serializes `run_end` writes. Acceptable for a local desktop tool. |
| Dark theme breaks existing pages | Theme toggle scoped per-page initially; existing pages opt-in by adding a class. |
| CLI-providers stop working in graph | `CLIChatModel` adapter ships in step 1 of build sequence; covered by `tests/agents/test_cli_chat_model.py` with subprocess mocking. |
| CLI provider can't produce structured output for critic | Critic node catches the structured-output failure, returns a hardcoded `Critique(verdict="REVISE", summary="...")` so the graph still progresses rather than crashing. User sees a warning in the UI run trace. |
| Files browser exposes paths outside THESIS_ROOT | Every path is `Path.resolve()`-checked against `THESIS_ROOT.resolve()` before any read/write — same pattern already used by `_safe_session_path`. Symlinks pointing outside are rejected. Test: `test_files_browser.py::test_path_traversal_blocked`. |
| Inline editor saves bad content over a draft | All `/files/save/<path>` writes go to a `<path>.tmp` first, then atomic `os.replace()`. On any exception the tmp is unlinked and the original is intact. |
| Error overlay leaks API keys in "copy as bug report" | `errors.format_error` runs the blob through a regex redactor for `(SK-|sk-ant|AIza|...)` patterns AND env-var keys matching `*_API_KEY|*_TOKEN|*_SECRET`. Test: `test_errors.py::test_no_secret_leakage` with a synthetic env. |
| Logs viewer slow at large JSONL volumes | Stream-read JSONL with offset/limit; never load full file. Cap displayed rows at 500/page. For thesis-scale this is fine (months of logs are tens of MB at most). |
| Originality check produces false positives | Default thresholds tuned to err toward "yellow flag, please review" rather than "red flag, plagiarism." Tool output explicitly says "potential match — human review required." |
| OpenAlex/Crossref API rate limits | Politeness pool: ≤2 requests/second, cached responses for 24h, batched paragraph queries. Use the `mailto=` polite-pool parameter on OpenAlex. |

## 12. UX Clarity — Descriptions & Help Text Everywhere

The audit found that descriptions/help already exist in the code, but the templates only render them inconsistently. The fix is small and concrete.

### Existing state

- `ToolSpec.description` — set for every tool in `TOOL_SPECS`. Rendered at the top of `/tools/<name>` (good).
- `Field.help` — set for some fields. Rendered in `tools.html` **only for checkbox fields** (line 29). Silently dropped for text/textarea/select/number/file_or_text. This is a one-line template bug equivalent.
- Hand-written pages (`/ask`, `/compare`, `/sessions`, `/index`) — have a short one-liner at top but no per-field help.
- Dashboard `/index.html` — tool catalog has no descriptions next to each item.

### Changes

1. **`tools.html` — render `fld.help` for every field type.** Single template edit. For each of textarea/select/number/text/file_or_text, add the same `{% if fld.help %}<p class="text-xs text-slate-500 mt-1">{{ fld.help }}</p>{% endif %}` block that checkbox already has.
2. **Populate `Field.help` on every field** in `TOOL_SPECS` that doesn't have it yet. Audit shows ~70% are empty. Each gets a one-sentence "what does this knob do, in plain English" string.
3. **Hand-written pages get inline help** — `/ask` adds `<details><summary>What is k / threshold?</summary>…</details>` blocks under the relevant slider labels. Same for `/compare` (model picker rationale), `/index` (collection / force / limit semantics).
4. **Dashboard `/index.html` tool catalog** — under each tool name, render its `spec.description` truncated to one line. The full description shows on hover or click-through.
5. **Workbench `/workbench` form** — every field gets a `?` tooltip icon that pops `fld.help` on click. Particularly important for iteration knobs and cost cap (otherwise users won't know what they do).
6. **Mode preset banner on Workbench** — a small "Quick / Standard / Best" hint above the role pickers explaining what the current preset implies (e.g., "Standard = sonnet + gemini-pro, 1 iteration max, $2 cost cap").

### Testing

- `tests/web/test_tools_template.py` — render each `ToolSpec`, assert `description` appears and at least N `help` strings appear in the HTML.
- `tests/web/test_field_help_coverage.py` — assert every `Field` in `TOOL_SPECS` has a non-empty `help`. Failing the test forces us to fill them all in.

### Effort

~250 lines across template edits + `TOOL_SPECS` help-string fills. Zero risk to existing flows. Shipped as step 1.5 in the build sequence (right after step 1 foundation, before the Workbench UI).

## 13. Originality / Plagiarism Check

A new tool that combines internal similarity (existing `paraphrase_check.py`) with an external academic check (OpenAlex + Crossref). Honest naming: "Originality check" not "Plagiarism check," because no free tool can prove plagiarism — only flag suspicious matches for human review.

### Module structure

```
research_assistant/
├── verification/
│   ├── originality.py            ← NEW: orchestrator that runs internal + external checks
│   ├── paraphrase_check.py       ← EXISTING: untouched, called by originality.py
│   └── external_match.py         ← NEW: OpenAlex + Crossref query helpers
└── web/
    └── tool_runner.py            ← + TOOL_SPECS entry for "originality" (in category "audit")
```

### `originality.py` flow

```python
def check_originality(
    draft_path: str,
    *,
    internal_threshold: float = 0.85,   # cosine sim against your library
    external_threshold: float = 0.80,   # cosine sim against OpenAlex/Crossref abstracts
    min_chars: int = 150,
    sources: tuple[str, ...] = ("internal", "openalex", "crossref"),
    embedding_model: str = DEFAULT_EMBED_MODEL,
) -> OriginalityReport:
    paragraphs = split_paragraphs(read_file(draft_path))
    paragraphs = [p for p in paragraphs if len(p) >= min_chars]

    report = OriginalityReport(paragraphs=[])
    for i, para in enumerate(paragraphs):
        entry = ParagraphReport(index=i, text=para, matches=[])
        if "internal" in sources:
            entry.matches += _internal_matches(para, internal_threshold)
        if "openalex" in sources:
            entry.matches += _openalex_matches(para, external_threshold)
        if "crossref" in sources:
            entry.matches += _crossref_matches(para, external_threshold)
        if entry.matches:
            report.paragraphs.append(entry)
    return report
```

### `external_match.py`

Two functions, both rate-limited and cached:

```python
def search_openalex(paragraph: str, *, limit: int = 5) -> list[ExternalMatch]:
    """
    Query OpenAlex /works with `search=` parameter, return top-N abstracts.
    Embed each returned abstract, return matches with cosine >= threshold.
    Polite pool: include mailto query param.
    """

def search_crossref(paragraph: str, *, limit: int = 5) -> list[ExternalMatch]:
    """
    Query Crossref /works with `query.bibliographic=` parameter.
    Same flow as OpenAlex.
    """
```

Cache: simple shelf at `~/.cache/research-assistant/external_match_cache.shelf` keyed by query hash. 24h TTL. Survives between runs.

### Schemas (Pydantic, in `verification/originality.py`)

```python
class ExternalMatch(BaseModel):
    source: Literal["internal", "openalex", "crossref"]
    similarity: float
    title: str
    authors: str | None
    year: int | None
    doi: str | None
    citekey: str | None       # only for internal matches
    excerpt: str               # snippet that matched
    url: str | None

class ParagraphReport(BaseModel):
    index: int
    text: str                  # the paragraph being checked
    matches: list[ExternalMatch]
    @property
    def severity(self) -> Literal["green", "yellow", "red"]:
        if not self.matches: return "green"
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

### CLI

```bash
ra-originality drafts/ch1.md
ra-originality drafts/ch1.md --sources internal,openalex   # skip Crossref
ra-originality drafts/ch1.md --internal-threshold 0.80 --external-threshold 0.75
ra-originality drafts/ch1.md --json
```

Added to `pyproject.toml` `[project.scripts]` as `ra-originality = "research_assistant.verification.originality:main"`.

### Web UI

New `TOOL_SPECS` entry in `tool_runner.py`:

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
        Field("sources", "Sources to check", "multiselect", flag="--sources",
              default="internal,openalex,crossref",
              options=("internal", "openalex", "crossref"),
              help=("Internal = your indexed Zotero papers. "
                    "OpenAlex / Crossref = published academic abstracts. "
                    "All three by default.")),
        Field("internal_threshold", "Internal similarity threshold", "number",
              flag="--internal-threshold", default=0.85, min=0.5, max=1.0, step=0.01,
              help="Higher = stricter. 0.85 catches near-verbatim; 0.75 catches close paraphrase."),
        Field("external_threshold", "External similarity threshold", "number",
              flag="--external-threshold", default=0.80, min=0.5, max=1.0, step=0.01,
              help="Cosine similarity between your paragraph and the matched abstract."),
        Field("min_chars", "Skip paragraphs shorter than", "number", flag="--min-chars",
              default=150, min=10, max=500, step=10,
              help="Tiny paragraphs are too noisy to check reliably."),
        Field("as_json", "JSON output", "checkbox", flag="--json"),
    ),
    long_running=True,
)
```

Result rendering reuses the same `_result.html` partial. A small badge component shows green/yellow/red severity per paragraph.

### Testing

- `tests/verification/test_originality.py` — fixture draft with one clean paragraph + one with verbatim copy from a fixture .bib entry; assert correct severity per paragraph.
- `tests/verification/test_external_match.py` — OpenAlex / Crossref clients mocked (no live API calls in CI); cache hit/miss tested; rate-limiter respected.
- `tests/test_originality_cli.py` — Click runner round-trip; `--json` schema validated.

### Effort

~600 lines: `originality.py` (~250), `external_match.py` (~150), tests (~200). New deps: nothing — uses `httpx` (already in `requirements.txt`) for HTTP and stdlib `shelve` for cache.

Shipped as step 2.5 in the build sequence — after CLI refactor (step 2), before Workbench (step 3) so it's exposed in the existing `/tools/originality` form first, and later gets a dedicated panel in Workbench's "Verify" tab.
