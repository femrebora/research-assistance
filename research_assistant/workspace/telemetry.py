"""Model orchestration dashboard — aggregate the AI call logs.

Every call routed through :func:`research_assistant.common.ask_model`
appends one JSON line to ``~/thesis/logs/YYYY-MM-DD.jsonl``. This module
turns those logs into the summary numbers Section 8 of
``research_assistant_development_findings.txt`` calls for:

* per-model totals (calls, tokens, cost, avg latency proxy)
* recent activity feed
* per-day cost trend for sparklines

Reading the existing log files keeps the dashboard a pure, side-effect-free
read; no schema migrations required.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from research_assistant.common import _COST_PER_1M, LOG_DIR

# ── Data model ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CallRecord:
    """One model call, parsed from a log line."""

    timestamp: datetime
    model_alias: str
    model_full: str
    via: str
    input_tokens: int
    output_tokens: int
    cost: float
    prompt_preview: str
    response_preview: str


@dataclass(frozen=True)
class ModelSummary:
    """Roll-up for a single model alias."""

    alias: str
    calls: int
    input_tokens: int
    output_tokens: int
    cost: float
    last_used: str  # ISO date, empty if unknown


@dataclass
class DashboardData:
    """Top-level structure consumed by the web template."""

    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    per_model: list[ModelSummary] = field(default_factory=list)
    recent: list[CallRecord] = field(default_factory=list)
    daily_cost: list[tuple[str, float]] = field(default_factory=list)
    log_dir: str = ""
    window_days: int = 30


# ── Public API ──────────────────────────────────────────────────────────────


def collect(
    *,
    window_days: int = 30,
    recent_limit: int = 20,
    log_dir: Path | None = None,
) -> DashboardData:
    """Walk the JSONL logs and return a :class:`DashboardData` snapshot.

    Parameters
    ----------
    window_days
        How many days back to scan. Defaults to 30 — enough for a thesis
        sprint without scanning years of history.
    recent_limit
        Most recent calls to include in the activity feed.
    log_dir
        Override the default ``~/thesis/logs`` location (useful in tests).
    """
    root = log_dir or LOG_DIR
    records = list(_iter_records(root, window_days=window_days))
    records.sort(key=lambda r: r.timestamp, reverse=True)

    total_input = sum(r.input_tokens for r in records)
    total_output = sum(r.output_tokens for r in records)
    total_cost = sum(r.cost for r in records)

    per_model = _summarise_models(records)
    daily_cost = _daily_cost_series(records, window_days)

    return DashboardData(
        total_calls=len(records),
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_cost=total_cost,
        per_model=per_model,
        recent=records[:recent_limit],
        daily_cost=daily_cost,
        log_dir=str(root),
        window_days=window_days,
    )


# ── Internals ───────────────────────────────────────────────────────────────


def _iter_records(root: Path, *, window_days: int):
    """Yield :class:`CallRecord` objects from JSONL files within the window."""
    if not root.exists():
        return
    cutoff = datetime.now(tz=UTC) - timedelta(days=window_days)
    for log_file in sorted(root.glob("*.jsonl")):
        log_date = _safe_date_from_name(log_file.name)
        if log_date and log_date < cutoff.date():
            continue
        try:
            with log_file.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    record = _parse_line(line)
                    if record is None:
                        continue
                    if record.timestamp >= cutoff:
                        yield record
        except OSError:
            continue


def _safe_date_from_name(name: str) -> date | None:
    """Log files are named ``YYYY-MM-DD.jsonl``; parse defensively."""
    stem = name.removesuffix(".jsonl")
    try:
        return date.fromisoformat(stem)
    except ValueError:
        return None


def _parse_line(line: str) -> CallRecord | None:
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None

    ts = _parse_ts(data.get("timestamp"))
    if ts is None:
        return None

    alias = str(data.get("model_alias") or "unknown")
    in_tokens = _as_int(data.get("input_tokens"))
    out_tokens = _as_int(data.get("output_tokens"))
    cost = _estimate_cost(alias, in_tokens, out_tokens)

    return CallRecord(
        timestamp=ts,
        model_alias=alias,
        model_full=str(data.get("model_full") or ""),
        via=str(data.get("via") or "api"),
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        cost=cost,
        prompt_preview=_preview(data.get("prompt")),
        response_preview=_preview(data.get("response")),
    )


def _parse_ts(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        ts = datetime.fromisoformat(value)
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _estimate_cost(alias: str, in_tokens: int, out_tokens: int) -> float:
    rates = _COST_PER_1M.get(alias)
    if not rates or (in_tokens == 0 and out_tokens == 0):
        return 0.0
    in_rate, out_rate = rates
    return (in_tokens / 1_000_000) * in_rate + (out_tokens / 1_000_000) * out_rate


def _preview(value: object, limit: int = 160) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = " ".join(value.split())
    return cleaned[:limit] + ("…" if len(cleaned) > limit else "")


def _summarise_models(records: list[CallRecord]) -> list[ModelSummary]:
    buckets: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "in": 0, "out": 0, "cost": 0.0, "last": ""}
    )
    for r in records:
        b = buckets[r.model_alias]
        b["calls"] += 1
        b["in"] += r.input_tokens
        b["out"] += r.output_tokens
        b["cost"] += r.cost
        iso = r.timestamp.date().isoformat()
        if iso > b["last"]:
            b["last"] = iso

    summaries = [
        ModelSummary(
            alias=alias,
            calls=v["calls"],
            input_tokens=v["in"],
            output_tokens=v["out"],
            cost=v["cost"],
            last_used=v["last"],
        )
        for alias, v in buckets.items()
    ]
    summaries.sort(key=lambda s: (-s.cost, -s.calls, s.alias))
    return summaries


def _daily_cost_series(
    records: list[CallRecord], window_days: int
) -> list[tuple[str, float]]:
    """Produce a continuous (date, cost) series so the chart has no gaps."""
    today = datetime.now(tz=UTC).date()
    days = [(today - timedelta(days=i)) for i in range(window_days - 1, -1, -1)]
    totals = defaultdict(float)
    for r in records:
        totals[r.timestamp.date()] += r.cost
    return [(d.isoformat(), round(totals[d], 4)) for d in days]
