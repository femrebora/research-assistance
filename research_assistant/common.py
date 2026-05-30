"""Shared helpers for thesis tools.

- Model routing via LiteLLM (Claude, Gemini, DeepSeek, GPT, local Ollama)
- Logging every call to ~/thesis/logs/YYYY-MM-DD.jsonl for disclosure
"""
from __future__ import annotations

import contextlib
import json
import os
import shlex
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from litellm import completion
from litellm.exceptions import (
    APIError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)

load_dotenv()

# Friendly model name -> LiteLLM model string.
# Edit these to whatever current model versions you want to use.
MODELS = {
    "claude":   "anthropic/claude-opus-4-7",
    "sonnet":   "anthropic/claude-sonnet-4-6",
    "haiku":    "anthropic/claude-haiku-4-5",
    "gemini":   "gemini/gemini-2.5-pro",
    "flash":    "gemini/gemini-2.5-flash",
    "deepseek": "deepseek/deepseek-chat",
    "gpt":      "openai/gpt-5",
    "gpt-mini": "openai/gpt-5-mini",
    "codex":    "openai/gpt-5",
    # Local via Ollama (LiteLLM-managed). Override the model name with OLLAMA_MODEL.
    # Examples: ollama/llama3.3, ollama/qwen2.5, ollama/mistral-nemo.
    "local":    os.getenv("OLLAMA_MODEL", "ollama/llama3.3"),
}

# ── CLI providers ────────────────────────────────────────────────────────────
#
# These aliases shell out to the model's own CLI tool instead of calling its
# API. Use them when you want to bill against a CLI subscription (Claude Code,
# Gemini CLI, Codex CLI) or run a local model via `ollama run`.
#
# The command template is a shell-quoted string. The prompt is appended as the
# final positional argument when the call is made. Override the binary or flags
# with the corresponding `*_CLI_CMD` environment variable in .env.
#
# Cost is recorded as $0 for CLI calls because billing happens at the
# subscription/local-compute layer, not per-token.
CLI_PROVIDERS = {
    "claude-cli": os.getenv("CLAUDE_CLI_CMD", "claude -p"),
    "gemini-cli": os.getenv("GEMINI_CLI_CMD", "gemini -p"),
    "codex-cli":  os.getenv("CODEX_CLI_CMD",  "codex exec"),
    "ollama-cli": os.getenv("OLLAMA_CLI_CMD", "ollama run llama3.3"),
}

# Merge CLI aliases into MODELS so every existing click.Choice picks them up
# automatically (ask.py, compare.py, critique.py, paraphrase.py, etc.).
MODELS.update({alias: f"cli:{cmd}" for alias, cmd in CLI_PROVIDERS.items()})

# Approximate cost per 1M tokens (input, output) for display.
# These are estimates — check provider pricing pages for exact numbers.
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
    "claude-cli": (0.0,  0.0),
    "gemini-cli": (0.0,  0.0),
    "codex-cli":  (0.0,  0.0),
    "ollama-cli": (0.0,  0.0),
}

CLI_TIMEOUT = int(os.getenv("CLI_TIMEOUT", "600"))

MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  # seconds, doubles each retry

_thesis_env = os.getenv("THESIS_ROOT")
if _thesis_env:
    THESIS_ROOT = Path(_thesis_env).expanduser().resolve()
else:
    THESIS_ROOT = Path.home() / "thesis"

LOG_DIR = THESIS_ROOT / "logs"


def _ensure_log_dir() -> None:
    """Create LOG_DIR on first use (not at import time).

    Deferring this avoids crashing the entire app at import time when
    THESIS_ROOT points to an inaccessible path (e.g. a stale hardcoded
    path in .env).
    """
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError) as e:
        import sys

        print(
            f"Error: Cannot create log directory at {LOG_DIR}\n"
            f"  Check that THESIS_ROOT in your .env file points to a writable location.\n"
            f"  Current value: {os.getenv('THESIS_ROOT', '(default)')}\n"
            f"  Expanded path: {THESIS_ROOT}\n"
            f"  Detail: {e}",
            file=sys.stderr,
        )
        raise


def ask_model(
    prompt: str,
    model: str = "claude",
    system: str | None = None,
    max_tokens: int = 4000,
    temperature: float = 0.3,
) -> dict:
    """Send a prompt to the named model. Returns dict with text + metadata.

    Every call is appended to today's log file for disclosure purposes.
    Retries on rate-limit and transient errors with exponential backoff.
    """
    if model not in MODELS:
        raise ValueError(
            f"Unknown model '{model}'. Available: {', '.join(MODELS.keys())}"
        )

    value = MODELS[model]
    if value.startswith("cli:"):
        return _ask_via_cli(prompt, model, value[4:], system=system)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = completion(
                model=MODELS[model],
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            break
        except RateLimitError as e:
            last_error = e
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF ** attempt
                time.sleep(wait)
        except (ServiceUnavailableError, Timeout) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF ** attempt
                time.sleep(wait)
        except APIError as e:
            raise RuntimeError(
                f"API error from {model} ({MODELS[model]}): {e}"
            ) from e
    else:
        raise RuntimeError(
            f"All {MAX_RETRIES} retries failed for {model}. "
            f"Last error: {last_error}"
        )

    text = response.choices[0].message.content
    usage = getattr(response, "usage", None)

    record = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "model_alias": model,
        "model_full": MODELS[model],
        "via": "api",
        "system": system,
        "prompt": prompt,
        "response": text,
        "input_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
        "output_tokens": getattr(usage, "completion_tokens", None) if usage else None,
    }
    _log(record)

    cost = _estimate_cost(model, record["input_tokens"], record["output_tokens"])

    return {
        "text": text,
        "model": MODELS[model],
        "input_tokens": record["input_tokens"],
        "output_tokens": record["output_tokens"],
        "cost": cost,
    }


def _ask_via_cli(
    prompt: str,
    model: str,
    cmd_str: str,
    system: str | None = None,
    timeout: int = CLI_TIMEOUT,
) -> dict:
    """Run a CLI tool with the prompt as its final positional argument.

    CLIs do not expose a standardized system-prompt slot, so any `system`
    string is prepended to the user prompt as a labeled header. Cost is
    recorded as $0 (subscription/local billing happens outside this layer).
    """
    cmd_parts = shlex.split(cmd_str)
    if not cmd_parts:
        raise RuntimeError(f"Empty CLI command for {model}")
    binary = cmd_parts[0]

    full_prompt = (
        f"[System]\n{system}\n\n[User]\n{prompt}" if system else prompt
    )
    full_cmd = [*cmd_parts, full_prompt]

    try:
        proc = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as e:
        env_var = model.upper().replace("-", "_") + "_CMD"
        raise RuntimeError(
            f"CLI binary '{binary}' not found in PATH. Install it, or override "
            f"the command with the {env_var} environment variable."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"CLI {binary} timed out after {timeout}s.") from e

    if proc.returncode != 0:
        stderr_tail = (proc.stderr or "").strip()[-500:]
        raise RuntimeError(
            f"CLI {binary} failed (exit {proc.returncode}): {stderr_tail}"
        )

    text = (proc.stdout or "").strip()

    record = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "model_alias": model,
        "model_full": cmd_str,
        "via": "cli",
        "system": system,
        "prompt": prompt,
        "response": text,
        "input_tokens": None,
        "output_tokens": None,
    }
    _log(record)

    return {
        "text": text,
        "model": cmd_str,
        "input_tokens": None,
        "output_tokens": None,
        "cost": 0.0,
    }


def open_in_editor(initial_text: str, suffix: str = ".md") -> str:
    """Open $EDITOR with `initial_text` pre-populated; return the saved content.

    Falls back to `nano` if $EDITOR is unset. Used by interactive review loops
    in paraphrase.py / critic.py / pipeline.py to let the user edit a model
    output before the next stage consumes it.
    """
    editor = os.getenv("EDITOR") or os.getenv("VISUAL") or "nano"
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8") as tf:
        tf.write(initial_text)
        tmp_path = tf.name
    try:
        subprocess.call([*shlex.split(editor), tmp_path])
        with open(tmp_path, encoding="utf-8") as f:
            return f.read()
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)


def _estimate_cost(alias: str, in_tokens: int | None, out_tokens: int | None) -> float | None:
    """Estimate cost in USD from token counts. Returns None if counts unavailable."""
    if in_tokens is None or out_tokens is None:
        return None
    rates = _COST_PER_1M.get(alias)
    if not rates:
        return None
    in_rate, out_rate = rates
    return (in_tokens / 1_000_000) * in_rate + (out_tokens / 1_000_000) * out_rate


def _log(record: dict) -> None:
    """Append one JSON line to today's log file."""
    _ensure_log_dir()
    today = datetime.now(tz=UTC).date().isoformat()
    log_file = LOG_DIR / f"{today}.jsonl"
    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _resolve_safe(path: str) -> Path:
    """Resolve a path against THESIS_ROOT, rejecting traversal escapes.

    Absolute paths are returned as-is (after expanduser + resolve) — only
    relative paths are sandboxed within THESIS_ROOT.
    """
    p = Path(path).expanduser()
    if p.is_absolute():
        return p.resolve()
    p = THESIS_ROOT / p
    resolved = p.resolve()
    thesis_resolved = THESIS_ROOT.resolve()
    if not str(resolved).startswith(str(thesis_resolved) + os.sep) and resolved != thesis_resolved:
        raise ValueError(
            f"Path '{path}' resolves outside THESIS_ROOT ({THESIS_ROOT})"
        )
    return resolved


def read_file(path: str) -> str:
    """Read a file, resolving ~ and relative paths against THESIS_ROOT."""
    return _resolve_safe(path).read_text(encoding="utf-8")


def save_file(path: str, content: str) -> Path:
    """Write content, resolving ~ and relative paths against THESIS_ROOT."""
    p = _resolve_safe(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p
