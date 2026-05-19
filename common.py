"""Shared helpers for thesis tools.

- Model routing via LiteLLM (Claude, Gemini, DeepSeek, GPT, local Ollama)
- Logging every call to ~/thesis/logs/YYYY-MM-DD.jsonl for disclosure
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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
    # Local via Ollama; uncomment and adjust if you run a local model:
    # "local":  "ollama/llama3.3",
}

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
}

MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  # seconds, doubles each retry

THESIS_ROOT = Path(os.getenv("THESIS_ROOT", str(Path.home() / "thesis")))
LOG_DIR = THESIS_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def ask_model(
    prompt: str,
    model: str = "claude",
    system: Optional[str] = None,
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
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "model_alias": model,
        "model_full": MODELS[model],
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


def _estimate_cost(alias: str, in_tokens: Optional[int], out_tokens: Optional[int]) -> Optional[float]:
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
    today = datetime.now(tz=timezone.utc).date().isoformat()
    log_file = LOG_DIR / f"{today}.jsonl"
    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_file(path: str) -> str:
    """Read a file, resolving ~ and relative paths against THESIS_ROOT."""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = THESIS_ROOT / p
    return p.read_text(encoding="utf-8")


def save_file(path: str, content: str) -> Path:
    """Write content, resolving ~ and relative paths against THESIS_ROOT."""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = THESIS_ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p
