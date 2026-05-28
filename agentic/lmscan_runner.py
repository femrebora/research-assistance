#!/usr/bin/env python3
"""lmscan_runner.py — optional integration with the lmscan AI detection library.

lmscan is an open-source GPTZero alternative with zero dependencies and full
offline support. It provides statistical AI detection + model fingerprinting.

Install: pip install lmscan
Docs: https://github.com/stef41/lmscan

This module wraps lmscan as a fallback/companion to quick_ai_score.py.
If lmscan is not installed, it degrades gracefully.
"""
from __future__ import annotations

import json
import subprocess

_LMSCAN_AVAILABLE = None


def _check_lmscan() -> bool:
    """Check if lmscan is installed and working."""
    global _LMSCAN_AVAILABLE
    if _LMSCAN_AVAILABLE is not None:
        return _LMSCAN_AVAILABLE

    try:
        result = subprocess.run(
            ["lmscan", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        _LMSCAN_AVAILABLE = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        _LMSCAN_AVAILABLE = False

    return _LMSCAN_AVAILABLE


def scan_text(text: str, timeout: int = 60) -> dict | None:
    """Run lmscan on text content. Returns parsed JSON result or None.

    lmscan provides:
    - overall_score: 0-1 (higher = more AI-like)
    - model_fingerprint: which LLM family (GPT-4, Claude, Gemini, etc.)
    - 12 statistical features: burstiness, Zipf deviation, entropy, slop density, etc.
    """
    if not _check_lmscan():
        return None

    try:
        result = subprocess.run(
            ["lmscan", "-", "--json"],
            input=text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return json.loads(result.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired,
            subprocess.SubprocessError, OSError):
        return None


def scan_file(path: str, timeout: int = 60) -> dict | None:
    """Run lmscan on a file. Returns parsed JSON result or None."""
    if not _check_lmscan():
        return None

    try:
        result = subprocess.run(
            ["lmscan", str(path), "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return json.loads(result.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired,
            subprocess.SubprocessError, OSError):
        return None


def format_lmscan_result(result: dict) -> str:
    """Format lmscan JSON output as a human-readable summary."""
    if not result:
        return ""

    lines = ["## External AI Detection (lmscan)"]

    overall = result.get("overall_score") or result.get("score")
    if overall is not None:
        score_10 = round(float(overall) * 10, 1)
        lines.append(f"- **Overall AI score**: {score_10}/10")

    fingerprint = result.get("model_fingerprint") or result.get("fingerprint")
    if fingerprint:
        lines.append(f"- **Likely model family**: {fingerprint}")

    # Individual features
    features = result.get("features") or result.get("stats") or {}
    if features:
        lines.append("- **Feature scores**:")
        for k, v in sorted(features.items()):
            if isinstance(v, (int, float)):
                lines.append(f"  - {k}: {round(float(v), 3)}")

    return "\n".join(lines)


def run_lmscan_on_paper(paper_path: str) -> dict:
    """Convenience function: run lmscan and return combined results.

    Returns {available: bool, result: dict|None, summary: str}
    """
    if not _check_lmscan():
        return {"available": False, "result": None, "summary": ""}

    result = scan_file(paper_path)
    if result is None:
        return {"available": True, "result": None, "summary": "lmscan failed to produce output."}

    return {
        "available": True,
        "result": result,
        "summary": format_lmscan_result(result),
    }
