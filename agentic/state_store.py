"""state_store.py — persistent pipeline state for the interactive web UI.

State lives at THESIS_ROOT/runs/<job_id>/state.json.
Events append to THESIS_ROOT/runs/<job_id>/events.jsonl for SSE replay.
An in-memory cache with short TTL avoids re-reading from disk on every SSE poll.
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
import time
from pathlib import Path

THESIS_ROOT = Path(os.getenv("THESIS_ROOT", str(Path.home() / "thesis")))
RUNS_DIR = THESIS_ROOT / "runs"

# In-memory cache (TTL ~30s to cover SSE polling without stale reads)
_cache: dict[str, dict] = {}
_cache_times: dict[str, float] = {}
_cache_lock = threading.Lock()
_job_locks: dict[str, threading.Lock] = {}
_job_locks_lock = threading.Lock()
CACHE_TTL = 30


def init_state(job_id: str, input_data: dict) -> dict:
    """Create a new pipeline state on disk. Returns the full state dict."""
    runs_dir = RUNS_DIR / job_id
    runs_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "job_id": job_id,
        "mode": input_data.get("mode", "code"),
        "status": "initializing",
        "code_path": input_data.get("code_path", ""),
        "user_summary": input_data.get("summary", ""),
        "topic": input_data.get("topic", ""),
        "output_dir": input_data.get("output_dir", ""),
        "max_rewrites": input_data.get("max_rewrites", 3),
        "technical_report": None,
        "draft": None,
        "sections": None,
        "assessment": None,
        "originality_score": None,
        "figures": None,
        "text_rewrite_count": 0,
        "figure_rewrite_count": 0,
        "agent_calls": [],
        "feedback_log": [],
        "created_at": time.time(),
        "started_at": None,
        "completed_at": None,
        "error": None,
    }
    _write_state(job_id, state)
    _cache_set(job_id, state)
    return state


def load_state(job_id: str) -> dict:
    """Load pipeline state from cache or disk."""
    cached = _cache_get(job_id)
    if cached is not None:
        return cached

    state_path = RUNS_DIR / job_id / "state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"No state for job {job_id}")

    state = json.loads(state_path.read_text(encoding="utf-8"))
    _cache_set(job_id, state)
    return state


def _get_job_lock(job_id: str) -> threading.Lock:
    with _job_locks_lock:
        if job_id not in _job_locks:
            _job_locks[job_id] = threading.Lock()
        return _job_locks[job_id]


def save_state(job_id: str, updates: dict):
    """Apply updates to the state and persist atomically. Thread-safe."""
    with _get_job_lock(job_id):
        state = load_state(job_id)
        state.update(updates)
        _write_state(job_id, state)
        _cache_set(job_id, state)


def append_event(job_id: str, event: dict):
    """Append an event to the job's event log for SSE replay."""
    event["_ts"] = time.time()
    events_path = RUNS_DIR / job_id / "events.jsonl"
    with open(events_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def get_events(job_id: str, since_index: int = 0) -> tuple[list[dict], int]:
    """Return events newer than since_index, and the new last index."""
    events_path = RUNS_DIR / job_id / "events.jsonl"
    if not events_path.exists():
        return [], 0

    with open(events_path, encoding="utf-8") as f:
        lines = f.readlines()

    new_events = []
    for line in lines[since_index:]:
        with contextlib.suppress(json.JSONDecodeError):
            new_events.append(json.loads(line.strip()))

    return new_events, len(lines)


def delete_state(job_id: str):
    """Remove all state and events for a job."""
    import shutil

    job_dir = RUNS_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    with _cache_lock:
        _cache.pop(job_id, None)
        _cache_times.pop(job_id, None)


def list_jobs() -> list[dict]:
    """List all jobs sorted by creation time (newest first)."""
    jobs = []
    runs_dir = RUNS_DIR
    if not runs_dir.exists():
        return jobs

    for job_dir in sorted(runs_dir.iterdir(), reverse=True):
        state_path = job_dir / "state.json"
        if not state_path.exists():
            continue
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            jobs.append({
                "id": state.get("job_id", job_dir.name),
                "status": state.get("status", "unknown"),
                "mode": state.get("mode", ""),
                "created_at": state.get("created_at", 0),
            })
        except (json.JSONDecodeError, OSError):
            pass
    return jobs


# ── internals ───────────────────────────────────────────────────────────

def _write_state(job_id: str, state: dict):
    """Atomic write: tmp file, then rename."""
    job_dir = RUNS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = job_dir / "state.json.tmp"
    real_path = job_dir / "state.json"
    tmp_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.rename(real_path)


def _cache_get(job_id: str) -> dict | None:
    with _cache_lock:
        ts = _cache_times.get(job_id, 0)
        if time.time() - ts < CACHE_TTL:
            return _cache.get(job_id)
    return None


def _cache_set(job_id: str, state: dict):
    with _cache_lock:
        _cache[job_id] = state
        _cache_times[job_id] = time.time()
