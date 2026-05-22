#!/usr/bin/env python3
"""disclose.py — generate an AI-usage disclosure from your call logs.

Every call from this toolkit appends one JSON line to
~/thesis/logs/YYYY-MM-DD.jsonl (see common.py). This script aggregates
those logs into a transparent disclosure statement suitable for thesis
appendices, journal submission forms, or conference disclosure fields.

Usage:
    ./disclose.py                                # all logs, markdown output
    ./disclose.py --since 2026-01-01 --until 2026-05-22
    ./disclose.py --venue elsevier               # opinionated prose template
    ./disclose.py --json --save logs/disclosure.json
    ./disclose.py --save thesis_disclosure.md
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from common import LOG_DIR, MODELS, save_file

console = Console()


VENUES = {
    "generic": (
        "## AI-assisted writing disclosure\n\n"
        "The author used the following AI language models during research and writing. "
        "All model usage was supervised; the author reviewed, edited, and verified every "
        "AI-generated output and remains responsible for the final text.\n"
    ),
    "elsevier": (
        "## Declaration of generative AI and AI-assisted technologies in the writing process\n\n"
        "During the preparation of this work the author used the following AI tools "
        "in order to assist with drafting, paraphrasing, critique, and citation auditing. "
        "After using these tools, the author reviewed and edited the content as needed and "
        "takes full responsibility for the content of the publication.\n"
    ),
    "springer": (
        "## Use of AI-generated content\n\n"
        "The author discloses the use of the following large language models during the "
        "research and writing process. AI was used to assist (not author) the work. "
        "Every output was inspected and revised by the author, who accepts full responsibility.\n"
    ),
    "acm": (
        "## ACM disclosure of generative AI use\n\n"
        "The author used the following generative AI systems in producing this work. "
        "AI-generated content was reviewed and revised by the author and is not represented as "
        "the work of the AI itself.\n"
    ),
    "thesis": (
        "## Appendix: AI-assisted writing disclosure\n\n"
        "In keeping with university policy on responsible use of AI in postgraduate research, "
        "the author discloses the following uses of large language models during this thesis. "
        "All AI outputs were reviewed, edited, and verified by the author, who takes sole "
        "responsibility for the final text and any errors.\n"
    ),
}


@dataclass(frozen=True)
class LogRecord:
    timestamp: str
    model_alias: str
    model_full: str
    prompt_chars: int
    response_chars: int
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    via: str = "api"  # "api" or "cli"; default for legacy logs without the field


def _iter_log_files(log_dir: Path = LOG_DIR):
    if not log_dir.exists():
        return []
    return sorted(log_dir.glob("*.jsonl"))


def _parse_date(s: str) -> Optional[date]:
    if not s:
        return None
    return datetime.fromisoformat(s).date()


def load_logs(
    since: Optional[date] = None,
    until: Optional[date] = None,
    log_dir: Path = LOG_DIR,
) -> list[LogRecord]:
    records: list[LogRecord] = []
    for log_file in _iter_log_files(log_dir):
        try:
            file_date = date.fromisoformat(log_file.stem)
        except ValueError:
            continue
        if since and file_date < since:
            continue
        if until and file_date > until:
            continue
        with log_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                records.append(
                    LogRecord(
                        timestamp=rec.get("timestamp", ""),
                        model_alias=rec.get("model_alias", "?"),
                        model_full=rec.get("model_full", "?"),
                        prompt_chars=len(rec.get("prompt") or ""),
                        response_chars=len(rec.get("response") or ""),
                        input_tokens=rec.get("input_tokens"),
                        output_tokens=rec.get("output_tokens"),
                        via=rec.get("via") or "api",
                    )
                )
    return records


# Approximate cost per 1M tokens (mirror of common._COST_PER_1M; kept here so
# disclose.py can format costs without importing that private symbol).
_COST_PER_1M = {
    "claude":   (15.00, 75.00),
    "sonnet":   (3.00,  15.00),
    "haiku":    (0.80,   4.00),
    "gemini":   (1.25,   5.00),
    "flash":    (0.075,  0.30),
    "deepseek": (0.27,   1.10),
    "gpt":      (1.25,  10.00),
    "gpt-mini": (0.15,   0.60),
    "codex":    (1.25,  10.00),
    "local":    (0.0,    0.0),
}


def aggregate(records: list[LogRecord]) -> dict:
    by_model: dict[str, dict] = defaultdict(
        lambda: {
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "model_full": "",
            "via": "api",
        }
    )
    by_route: dict[str, int] = {"api": 0, "cli": 0}
    timestamps = []
    for r in records:
        m = by_model[r.model_alias]
        m["calls"] += 1
        m["model_full"] = r.model_full
        m["via"] = r.via
        if r.input_tokens:
            m["input_tokens"] += r.input_tokens
        if r.output_tokens:
            m["output_tokens"] += r.output_tokens
        if r.via == "api":
            rates = _COST_PER_1M.get(r.model_alias)
            if rates and r.input_tokens and r.output_tokens:
                in_rate, out_rate = rates
                m["cost"] += (r.input_tokens / 1_000_000) * in_rate
                m["cost"] += (r.output_tokens / 1_000_000) * out_rate
        by_route[r.via] = by_route.get(r.via, 0) + 1
        if r.timestamp:
            timestamps.append(r.timestamp)

    total = {
        "calls": sum(m["calls"] for m in by_model.values()),
        "input_tokens": sum(m["input_tokens"] for m in by_model.values()),
        "output_tokens": sum(m["output_tokens"] for m in by_model.values()),
        "cost": sum(m["cost"] for m in by_model.values()),
    }
    first_ts = min(timestamps) if timestamps else None
    last_ts = max(timestamps) if timestamps else None

    return {
        "by_model": dict(by_model),
        "by_route": by_route,
        "total": total,
        "first_call": first_ts,
        "last_call": last_ts,
    }


def render_markdown(stats: dict, venue: str = "generic") -> str:
    header = VENUES.get(venue, VENUES["generic"])
    if not stats["by_model"]:
        return header + "\nNo AI model calls were recorded.\n"

    lines = [header]
    lines.append(
        f"_Period: {stats['first_call'] or 'unknown'} → {stats['last_call'] or 'unknown'}_\n"
    )
    lines.append("### Models used\n")
    lines.append("| Alias | Route | Underlying model | Calls | Input tokens | Output tokens | Est. cost (USD) |")
    lines.append("|---|---|---|---:|---:|---:|---:|")
    for alias, m in sorted(stats["by_model"].items(), key=lambda kv: -kv[1]["calls"]):
        cost_cell = f"${m['cost']:.2f}" if m["via"] == "api" else "n/a (CLI subscription)"
        tokens_in = f"{m['input_tokens']:,}" if m["via"] == "api" else "—"
        tokens_out = f"{m['output_tokens']:,}" if m["via"] == "api" else "—"
        lines.append(
            f"| `{alias}` | {m['via']} | `{m['model_full']}` | {m['calls']} | "
            f"{tokens_in} | {tokens_out} | {cost_cell} |"
        )

    total = stats["total"]
    route = stats.get("by_route", {})
    route_breakdown = (
        f" ({route.get('api', 0)} via API, {route.get('cli', 0)} via CLI subscription)"
        if route else ""
    )
    lines.append(
        f"\n**Totals:** {total['calls']} model calls{route_breakdown} · "
        f"{total['input_tokens']:,} input tokens · "
        f"{total['output_tokens']:,} output tokens · "
        f"≈ ${total['cost']:.2f} estimated API cost "
        f"(CLI-routed calls are billed via subscription).\n"
    )
    lines.append(
        "Tools used: `ask`, `compare`, `paraphrase`, `critic`, `critique`, `claim_verify`, "
        "`verify`, `audit`, `coherence`, `ideas`, `outline`, `researcher`, `evidence`, "
        "`discover`, `pipeline` (this repository).\n"
    )
    lines.append(
        "Per-call logs (timestamp, model, prompt, response, tokens) are retained at "
        f"`{LOG_DIR}/YYYY-MM-DD.jsonl` and available on request.\n"
    )
    return "\n".join(lines)


def _render_console(stats: dict, venue: str) -> None:
    if not stats["by_model"]:
        console.print("[yellow]No AI model calls recorded. Run some queries first.[/yellow]")
        return

    summary = Table(title="AI usage disclosure", show_header=True)
    summary.add_column("Alias", style="cyan", no_wrap=True)
    summary.add_column("Route", style="bold", no_wrap=True)
    summary.add_column("Model", style="dim", no_wrap=True)
    summary.add_column("Calls", style="green", justify="right")
    summary.add_column("In tokens", justify="right")
    summary.add_column("Out tokens", justify="right")
    summary.add_column("Cost (USD)", justify="right")

    for alias, m in sorted(stats["by_model"].items(), key=lambda kv: -kv[1]["calls"]):
        is_cli = m["via"] == "cli"
        summary.add_row(
            alias,
            "cli" if is_cli else "api",
            m["model_full"],
            str(m["calls"]),
            "—" if is_cli else f"{m['input_tokens']:,}",
            "—" if is_cli else f"{m['output_tokens']:,}",
            "subscription" if is_cli else f"${m['cost']:.2f}",
        )
    console.print(summary)

    total = stats["total"]
    console.print(
        f"\n[bold]Period:[/bold] {stats['first_call']} → {stats['last_call']}"
    )
    console.print(
        f"[bold]Total:[/bold] {total['calls']} calls · "
        f"{total['input_tokens']:,} in · {total['output_tokens']:,} out · "
        f"~${total['cost']:.2f} ({venue} template)\n"
    )


@click.command()
@click.option("--since", default=None, help="ISO date (YYYY-MM-DD); only include logs on/after.")
@click.option("--until", default=None, help="ISO date (YYYY-MM-DD); only include logs on/before.")
@click.option("--venue", default="generic",
              type=click.Choice(list(VENUES.keys())),
              help="Disclosure template style.")
@click.option("--json", "as_json", is_flag=True, help="Output machine-readable JSON.")
@click.option("--save", "-o", default=None, help="Save the rendered disclosure to a file.")
@click.option("--log-dir", default=None, help="Override log directory (default: ~/thesis/logs).")
def main(since, until, venue, as_json, save, log_dir):
    """Generate an AI-usage disclosure statement from local call logs."""
    log_path = Path(log_dir).expanduser() if log_dir else LOG_DIR
    records = load_logs(
        since=_parse_date(since),
        until=_parse_date(until),
        log_dir=log_path,
    )
    stats = aggregate(records)

    if as_json:
        payload = {
            "first_call": stats["first_call"],
            "last_call": stats["last_call"],
            "total": stats["total"],
            "by_model": stats["by_model"],
            "log_dir": str(log_path),
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    else:
        text = render_markdown(stats, venue=venue)

    if save:
        path = save_file(save, text)
        console.print(f"[green]Saved disclosure to: {path}[/green]\n")

    if as_json:
        click.echo(text)
    else:
        _render_console(stats, venue)
        console.print(Markdown(text))


if __name__ == "__main__":
    main()
