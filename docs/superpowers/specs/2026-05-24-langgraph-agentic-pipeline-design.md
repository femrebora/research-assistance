# LangGraph Agentic Pipeline + Unified Web Workbench — Design

**Date:** 2026-05-24
**Status:** Approved (pending user spec review)
**Author:** Brainstorming session with `superpowers:brainstorming`

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
│   ├── models.py                  ← ChatLiteLLM factory; bridges MODELS dict → LangChain
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
    ├── app.py                     ← + routes: /workbench, /workbench/run, /workbench/stream/<id>, /runs, /runs/<id>, /usage, /settings
    ├── workbench.py               ← NEW: SSE bridge between graph and HTTP
    ├── runs_store.py              ← NEW: JSONL writer + SQLite index (dual storage)
    ├── usage_store.py             ← NEW: aggregations over ~/thesis/logs/*.jsonl
    ├── settings_store.py          ← NEW: user prefs in ~/.config/research-assistant/settings.json
    ├── templates/
    │   ├── base.html              ← + nav links + dark theme toggle
    │   ├── workbench.html         ← NEW
    │   ├── workbench_event.html   ← NEW (HTMX SSE fragment per node event)
    │   ├── runs.html              ← NEW
    │   ├── run_detail.html        ← NEW
    │   ├── usage.html             ← NEW
    │   └── settings.html          ← NEW
    └── static/
        ├── style.css              ← + dark-mode workbench styles
        └── workbench.js           ← ~50 lines: SSE event handling, graph state updates
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
- `pydantic>=2.0` — already implied by langchain ecosystem

No new runtime dep for SQLite (stdlib `sqlite3`).

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
- API-key health check — POSTs to each configured provider with a tiny ping, reports OK / fail
- Index status (last indexed, chunk count) — already available, just surfaced here
- Theme preference (light/dark)

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
| Legacy CLI | `tests/test_pipeline_legacy.py` | `ra-pipeline ... --legacy` produces output byte-identical to pre-refactor for canned inputs |

**Coverage target:** 80%+ on `agents/`, 70%+ on new `web/` code.

## 10. Build Sequence

1. **Foundation** — `agents/` package: state, schemas, models, policies, observability, all 5 nodes, graph wiring. Unit tests per node + graph.
2. **CLI refactor** — `pipeline.py` becomes thin wrapper; add new flags; `--legacy` test passes.
3. **Workbench UI** — `/workbench` page + SSE bridge + `runs_store.py` (JSONL write only). Hand-test end-to-end.
4. **Runs UI** — SQLite index + `/runs` list + `/runs/<id>` detail + fork.
5. **Usage + Settings** — dashboards + presets + API health check.
6. **Test hardening + docs** — fill coverage gaps, update README sections.

Each step is independently shippable. After step 2 the CLI is already improved; after step 3 the Workbench is usable; after step 4 history works; after steps 5-6 the experience is complete.

## 11. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| LangGraph version churn | Pin `>=0.2,<0.3`. All graph wiring isolated in `graphs/writing_pipeline.py` (~150 lines) — re-pinning is a single-file change. |
| `langchain-litellm` cost-logging double-counts vs. existing `common.py` logger | One logging path only — disable litellm's internal callback, keep `common.py`'s. Asserted in tests. |
| Tool-using writer infinite loop | LangGraph already enforces a recursion limit per run; set to 10. Cost cap is the hard backstop. |
| SSE connection drops mid-run | Run continues server-side; client reconnects with `Last-Event-ID` and replays from JSONL. Standard SSE pattern. |
| SQLite write contention from concurrent runs | Single writer thread per process; web app serializes `run_end` writes. Acceptable for a local desktop tool. |
| Dark theme breaks existing pages | Theme toggle scoped per-page initially; existing pages opt-in by adding a class. |
