"""benchmark_parser.py — discover and parse benchmark results from a codebase.

Scans a code directory for common benchmark output formats (JSON, CSV, TSV,
plain-text timing logs) and extracts structured performance data for the Writer.
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

BENCHMARK_FILENAMES = [
    "benchmark*.json", "benchmark*.csv", "benchmark*.tsv",
    "results*.json", "results*.csv", "results*.tsv",
    "performance*.json", "performance*.csv", "performance*.tsv",
    "timing*.json", "timing*.csv", "timing*.tsv",
    "accuracy*.json", "accuracy*.csv", "accuracy*.tsv",
    "eval*.json", "eval*.csv", "eval*.tsv",
    "metrics*.json", "metrics*.csv", "metrics*.tsv",
    "*_benchmark*.json", "*_benchmark*.csv", "*_benchmark*.tsv",
]

TIMING_PATTERNS = [
    re.compile(r"(?:elapsed|wall.clock|runtime|execution.time|total.time)[:\s]*([\d.]+)\s*(?:s|sec|seconds?)", re.IGNORECASE),
    re.compile(r"([\d.]+)\s*(?:s|sec|seconds?)\s*(?:elapsed|total|wall)", re.IGNORECASE),
    re.compile(r"(?:processed|scanned|analyzed)\s+(\d+)\s+(?:files|records|entries|reads|proteins|sequences)", re.IGNORECASE),
    re.compile(r"(?:accuracy|precision|recall|f1|f.score)[:\s]*([\d.]+)", re.IGNORECASE),
]

MAX_RESULT_SIZE = 200_000  # chars
MAX_ROWS = 50


def discover_benchmarks(code_path: str) -> list[Path]:
    """Find benchmark files in a code directory. Returns sorted list of paths."""
    root = Path(code_path).expanduser().resolve()
    if not root.exists():
        return []

    results = []
    for pattern in BENCHMARK_FILENAMES:
        for match in root.rglob(pattern):
            if match.is_file() and match.stat().st_size < 10 * 1024 * 1024:
                results.append(match)

    # Deduplicate and sort by name
    seen = set()
    unique = []
    for p in sorted(results, key=lambda x: x.name):
        if p not in seen:
            seen.add(p)
            unique.append(p)

    return unique[:20]


def parse_benchmark_file(path: Path) -> dict:
    """Parse a single benchmark file. Returns {filename, format, data, rows}."""
    try:
        raw = path.read_text(encoding="utf-8")[:MAX_RESULT_SIZE]
    except (OSError, UnicodeDecodeError):
        return {"filename": path.name, "error": "Could not read file", "format": "unknown"}

    # JSON
    try:
        data = json.loads(raw)
        return {
            "filename": path.name,
            "format": "json",
            "data": _flatten_json(data),
            "rows": 1,
        }
    except (json.JSONDecodeError, ValueError):
        pass

    # CSV/TSV
    try:
        dialect = csv.Sniffer().sniff(raw[:4096])
        reader = csv.DictReader(io.StringIO(raw), dialect=dialect)
        rows = []
        for i, row in enumerate(reader):
            if i >= MAX_ROWS:
                break
            rows.append(row)
        if rows:
            return {
                "filename": path.name,
                "format": "csv",
                "headers": list(rows[0].keys()),
                "data": rows,
                "rows": len(rows),
            }
    except (csv.Error, UnicodeDecodeError):
        pass

    # Plain text — scrape timing/accuracy data
    scraped = _scrape_timing_metrics(raw)
    if scraped:
        return {
            "filename": path.name,
            "format": "text",
            "data": scraped,
            "rows": len(scraped),
        }

    return {"filename": path.name, "format": "unknown", "error": "Unrecognized format"}


def _flatten_json(data, max_depth: int = 4) -> dict:
    """Flatten nested JSON into a dict of key: value strings."""
    result = {}

    def _walk(obj, prefix="", depth=0):
        if depth > max_depth:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                _walk(v, f"{prefix}{k}.", depth + 1)
        elif isinstance(obj, list):
            for i, v in enumerate(obj[:10]):
                _walk(v, f"{prefix}[{i}].", depth + 1)
        elif isinstance(obj, (int, float, bool)):
            result[prefix.rstrip(".")] = str(obj)
        elif obj is not None:
            s = str(obj)
            if len(s) < 500:
                result[prefix.rstrip(".")] = s

    _walk(data)
    return result


def _scrape_timing_metrics(text: str) -> list[dict]:
    """Extract timing and accuracy metrics from plain text."""
    hits = []
    for pat in TIMING_PATTERNS:
        for m in pat.finditer(text):
            hits.append({
                "metric": m.group(0).strip(),
                "pattern": pat.pattern[:60],
            })
    return hits[:30]


def format_benchmarks_for_prompt(benchmark_results: list[dict]) -> str:
    """Format parsed benchmark data for injection into the Writer prompt."""
    if not benchmark_results:
        return ""

    sections = ["## Benchmark Data (from codebase)\n"]

    for result in benchmark_results:
        filename = result.get("filename", "unknown")
        fmt = result.get("format", "unknown")

        if "error" in result:
            continue

        sections.append(f"\n### {filename} ({fmt})\n")

        if fmt == "json":
            data = result.get("data", {})
            if isinstance(data, dict):
                for k, v in list(data.items())[:40]:
                    if v and len(str(v)) < 200:
                        sections.append(f"- **{k}**: {v}")
                if len(data) > 40:
                    sections.append(f"- ... ({len(data) - 40} more entries)")

        elif fmt == "csv":
            headers = result.get("headers", [])
            data = result.get("data", [])
            sections.append(f"Columns: {', '.join(headers[:15])}")
            sections.append(f"Rows: {result.get('rows', len(data))}")
            if data:
                sections.append("")
                sections.append("| " + " | ".join(headers[:8]) + " |")
                sections.append("|" + "|".join(["---"] * min(8, len(headers))) + "|")
                for row in data[:15]:
                    vals = [str(row.get(h, ""))[:40] for h in headers[:8]]
                    sections.append("| " + " | ".join(vals) + " |")

        elif fmt == "text":
            data = result.get("data", [])
            if isinstance(data, list):
                for item in data[:20]:
                    sections.append(f"- {item.get('metric', str(item))}")

    return "\n".join(sections)


def parse_benchmarks(code_path: str) -> str:
    """Full pipeline: discover, parse, and format benchmark data for prompts."""
    files = discover_benchmarks(code_path)
    results = [parse_benchmark_file(f) for f in files]
    return format_benchmarks_for_prompt([r for r in results if "error" not in r])
