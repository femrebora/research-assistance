# UI-First Control Plane for research-assistant

**Date:** 2026-05-29
**Status:** Approved

## Goal

Make research-assistant controllable from the browser after installation, surface
the already-wired CLI model providers (codex/gemini/claude/ollama), improve the
web UX, verify the whole platform works, and push the result to `origin/master`.

## Baseline (verified before work)

- 204 tests pass; 2 fail only because `langgraph` (optional PaperForge dep) is not installed.
- ~67 ruff auto-fixable findings repo-wide (mostly intentional `RUF001` unicode in prompt prose).
- CLI providers (`claude-cli`, `gemini-cli`, `codex-cli`, `ollama-cli`) already exist in
  `research_assistant/common.py` and are merged into `MODELS`. All four CLIs are installed locally.
- PaperForge web blueprint exists in `agentic/web_server.py` but is not registered in the main
  Flask app (`research_assistant/web/app.py`) or shown in the nav.
- Config (API keys, CLI commands, paths) lives only in `.env`; nothing in the browser controls it.

## Scope

### 0. Verification & cleanup (precondition)
- Install `langgraph` into the venv to clear the 2 failing integration tests.
- `ruff check --fix` for safe fixes; extend per-file `RUF001` ignores in `pyproject.toml` for
  prompt-prose modules rather than editing prompt text. End lint-clean, suite green.

### 1. Providers page (`/providers`) — new
- Auto-detect each CLI by resolving its configured `*_CLI_CMD` binary via `shutil.which`;
  show found/missing, resolved path, exact command.
- Show API providers as key-configured/not-set (masked).
- Per-provider "Test" button runs a tiny prompt through `ask_model(<alias>)`; reports
  success / latency / output snippet.
- Verify CLI aliases appear in every model dropdown (they flow via `MODELS`).

### 2. Settings page (`/settings`) — new (hybrid)
- Secrets (API/Zotero keys): read-only status, masked, never editable or revealed in browser.
- Editable config: `THESIS_ROOT`, `ZOTERO_STORAGE`, `ZOTERO_USER_ID`, the four `*_CLI_CMD`,
  `OLLAMA_MODEL`, `CLI_TIMEOUT`, `EDITOR`. Written back to `.env`, preserving all other lines;
  secret lines never touched.
- "Takes effect on restart" notice for import-time vars.

### 3. PaperForge integration
- Register `paperforge_bp` in the main app, add nav link, confirm templates + SSE progress
  work in the unified app. Both code->paper and topic->review runnable from the browser.

### 4. UI/UX
- Restructure `base.html` nav into groups: Research / Workspace / Generate / Config, with
  active-state highlighting.
- Polish `style.css` (spacing, cards, status pills, responsive); keep lightweight
  server-rendered Flask aesthetic — no SPA framework.
- Dashboard surfaces provider/config health at a glance.

### 5. Tests
- Add `tests/web` coverage for `/providers`, `/settings` (GET + POST round-trip on a temp `.env`,
  asserting secrets are never written/echoed), and PaperForge registration.

### 6. Finalize
- Full suite green, ruff clean, app boots with all routes returning 200 (smoke test).
- Commit as Furkan Emre Bora <furkanemrebora@gmail.com>, no Claude attribution, push to `origin/master`.

## Non-goals (YAGNI)
No auth system, no database, no SPA rewrite, no new model providers beyond what exists.
