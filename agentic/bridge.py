"""Bridge layer — routes agent calls to local CLI tools and manages caches.

Uses the user's installed CLIs instead of API calls:
  - Claude models → claude CLI (Claude Code)
  - DeepSeek models → use-deepseek bash function + claude CLI
  - Gemini models → gemini CLI
"""
from __future__ import annotations

import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Optional

THESIS_ROOT = Path(os.getenv("THESIS_ROOT", str(Path.home() / "thesis")))
CACHE_DIR = THESIS_ROOT / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT = 300  # seconds per agent call


def call_agent(
    prompt: str,
    model: str = "claude",
    system: Optional[str] = None,
    temperature: float = 0.3,
) -> dict:
    """Call a local AI CLI and return {text, model, input_tokens, output_tokens, cost}.

    Routes to the appropriate CLI based on model alias:
      claude, sonnet, haiku → claude -p
      deepseek              → use-deepseek && claude -p
      gemini, flash         → gemini -p
    """
    full_prompt = prompt
    if system:
        full_prompt = f"System instructions: {system}\n\n---\n\nUser query: {prompt}"

    if model in ("claude", "sonnet", "haiku"):
        return _call_claude(full_prompt, model)
    elif model == "deepseek":
        return _call_deepseek(full_prompt)
    elif model in ("gemini", "flash"):
        return _call_gemini(full_prompt)
    else:
        raise ValueError(f"Unknown model '{model}'. Available: claude, sonnet, haiku, deepseek, gemini, flash")


def _call_claude(prompt: str, model: str) -> dict:
    """Call Claude via the `claude` CLI."""
    cmd = f"claude -p {shlex.quote(prompt)} --bare --allowedTools '' --output-format json"
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=os.environ.copy(),
        )
        output = result.stdout.strip()
        if not output:
            output = result.stderr.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        output = "(timed out)"
    except Exception as e:
        output = f"(error: {e})"

    return {
        "text": output,
        "model": model,
        "input_tokens": None,
        "output_tokens": None,
        "cost": None,
    }


def _call_deepseek(prompt: str) -> dict:
    """Call DeepSeek by sourcing use-deepseek before invoking claude."""
    cmd = (
        f"bash -c 'source ~/.bashrc; use-deepseek; "
        f"claude -p {shlex.quote(prompt)} --bare --allowedTools \"\"'"
    )
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=os.environ.copy(),
        )
        output = result.stdout.strip()
        if not output:
            output = result.stderr.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        output = "(timed out)"
    except Exception as e:
        output = f"(error: {e})"

    return {
        "text": output,
        "model": "deepseek",
        "input_tokens": None,
        "output_tokens": None,
        "cost": None,
    }


def _call_gemini(prompt: str) -> dict:
    """Call Gemini via the `gemini` CLI."""
    cmd = f"gemini -p {shlex.quote(prompt)} -o text -y --skip-trust"
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=os.environ.copy(),
        )
        # Gemini prints warnings to stderr; the actual response is on stdout
        output = result.stdout.strip()
        if not output:
            output = result.stderr.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        output = "(timed out)"
    except Exception as e:
        output = f"(error: {e})"

    return {
        "text": output,
        "model": "gemini",
        "input_tokens": None,
        "output_tokens": None,
        "cost": None,
    }


def load_cache(path: str) -> Optional[str]:
    """Load cached content from a file. Returns None if missing."""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = CACHE_DIR / p
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def save_cache(path: str, content: str) -> Path:
    """Save content to a cache file. Returns the path."""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = CACHE_DIR / p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def cache_age_days(path: str) -> Optional[float]:
    """Return age of cache file in days, or None if missing."""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = CACHE_DIR / p
    if not p.exists():
        return None
    return (time.time() - p.stat().st_mtime) / 86400


def is_cache_fresh(path: str, max_age_days: int = 7) -> bool:
    """Check if a cache file exists and is within max_age_days."""
    age = cache_age_days(path)
    return age is not None and age <= max_age_days
