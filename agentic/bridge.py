"""Bridge layer — routes agent calls to local CLI tools and manages caches.

Claude → claude CLI (--bare, JSON output, works correctly).
DeepSeek → direct HTTP API (OpenAI-compatible /v1/chat/completions).
Gemini → gemini CLI (--approval-mode plan, no tool execution).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

THESIS_ROOT = Path(os.getenv("THESIS_ROOT", str(Path.home() / "thesis")))
CACHE_DIR = THESIS_ROOT / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT = 600  # seconds per agent call

# DeepSeek API config
DEEPSEEK_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"  # v3-equivalent, fast and cheap
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# Gemini API config (optional fallback — use CLI for now)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

FALLBACK_CHAIN = ["deepseek", "gemini"]

MIN_TEXT_LENGTH = 50
ERROR_MARKERS = ("(timed out)", "(error:", "(no output)", "PermissionError",
                 "insufficient_quota", "rate_limit", "overloaded")


def _is_broken(text: str) -> bool:
    """Check if a model response is broken/empty/short enough to warrant fallback."""
    if not text or len(text) < MIN_TEXT_LENGTH:
        return True
    low = text.lower()
    return any(m.lower() in low for m in ERROR_MARKERS)


def call_agent(
    prompt: str,
    model: str = "claude",
    system: str | None = None,
    temperature: float = 0.3,
    fallback: list[str] | bool | None = None,
) -> dict:
    """Call an AI model and return {text, model, input_tokens, output_tokens, cost}.

    Claude → claude CLI, DeepSeek → direct API, Gemini → gemini CLI.
    Falls back when primary response is broken/empty/timed-out.
    """
    primary = _dispatch(prompt, model, system)
    if not _is_broken(primary.get("text", "")):
        return primary

    chain = FALLBACK_CHAIN if fallback is True else (fallback if isinstance(fallback, list) else [])
    for fb_model in chain:
        if fb_model == model:
            continue
        print(f"  ⚠ {model} response broken ({len(primary.get('text',''))} chars), "
              f"falling back to {fb_model}...", file=sys.stderr)
        fb_result = _dispatch(prompt, fb_model, system)
        if not _is_broken(fb_result.get("text", "")):
            fb_result["fallback_from"] = model
            return fb_result

    return primary


def _dispatch(prompt: str, model: str, system: str | None = None) -> dict:
    """Route to the right backend."""
    if model in ("claude", "sonnet", "haiku"):
        full = f"System instructions: {system}\n\n---\n\nUser query: {prompt}" if system else prompt
        return _call_claude(full, model)
    elif model == "deepseek":
        return _call_deepseek(prompt, system)
    elif model in ("gemini", "flash"):
        full = f"System instructions: {system}\n\n---\n\nUser query: {prompt}" if system else prompt
        return _call_gemini(full)
    else:
        raise ValueError(
            f"Unknown model '{model}'. "
            f"Available: claude, sonnet, haiku, deepseek, gemini, flash")


def _parse_claude_json(stdout: str) -> dict:
    """Parse Claude CLI JSON output. Returns {text, input_tokens, output_tokens, cost}."""
    try:
        data = json.loads(stdout)
        return {
            "text": data.get("result", stdout),
            "input_tokens": data.get("usage", {}).get("input_tokens"),
            "output_tokens": data.get("usage", {}).get("output_tokens"),
            "cost": data.get("total_cost_usd"),
        }
    except (json.JSONDecodeError, TypeError):
        return {"text": stdout, "input_tokens": None, "output_tokens": None, "cost": None}


def _call_claude(prompt: str, model: str) -> dict:
    """Call Claude via the `claude` CLI."""
    cmd = ["claude", "-p", prompt, "--bare", "--output-format", "json"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=os.environ.copy(),
        )
        stdout = result.stdout.strip()
        if not stdout:
            stdout = result.stderr.strip() or "(no output)"
            parsed = {"text": stdout, "input_tokens": None, "output_tokens": None, "cost": None}
        else:
            parsed = _parse_claude_json(stdout)
    except subprocess.TimeoutExpired:
        parsed = {"text": "(timed out)", "input_tokens": None, "output_tokens": None, "cost": None}
    except Exception as e:
        parsed = {"text": f"(error: {e})", "input_tokens": None, "output_tokens": None, "cost": None}

    return {"text": parsed["text"], "model": model,
            "input_tokens": parsed["input_tokens"], "output_tokens": parsed["output_tokens"],
            "cost": parsed["cost"]}


def _call_deepseek(prompt: str, system: str | None = None) -> dict:
    """Call DeepSeek via direct OpenAI-compatible API (bypasses CLI coding context)."""
    api_key = DEEPSEEK_API_KEY or os.getenv("ANTHROPIC_AUTH_TOKEN", "")
    if not api_key:
        return {"text": "(error: no DeepSeek API key — set ANTHROPIC_AUTH_TOKEN)",
                "model": "deepseek", "input_tokens": None, "output_tokens": None, "cost": None}

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = json.dumps({
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 8000,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{DEEPSEEK_BASE}/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        choice = data["choices"][0]
        text = choice["message"]["content"]
        usage = data.get("usage", {})
        return {
            "text": text,
            "model": data.get("model", "deepseek-chat"),
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
            "cost": None,  # DeepSeek pricing varies
        }
    except urllib.error.HTTPError as e:
        return {"text": f"(HTTP {e.code} from DeepSeek API)", "model": "deepseek",
                "input_tokens": None, "output_tokens": None, "cost": None}
    except Exception as e:
        return {"text": f"(error: {e})", "model": "deepseek",
                "input_tokens": None, "output_tokens": None, "cost": None}


def _call_gemini(prompt: str) -> dict:
    """Call Gemini via the `gemini` CLI."""
    cmd = ["gemini", "-p", prompt, "--approval-mode", "plan", "--skip-trust"]
    try:
        result = subprocess.run(
            cmd,
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

    return {"text": output, "model": "gemini",
            "input_tokens": None, "output_tokens": None, "cost": None}


def load_cache(path: str) -> str | None:
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


def cache_age_days(path: str) -> float | None:
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
