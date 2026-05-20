"""Bridge layer — wraps common.ask_model and manages knowledge caches."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from common import ask_model, THESIS_ROOT

CACHE_DIR = THESIS_ROOT / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def call_agent(
    prompt: str,
    model: str = "claude",
    system: Optional[str] = None,
    temperature: float = 0.3,
) -> dict:
    """Call an AI model via common.ask_model. Returns {text, model, input_tokens, output_tokens, cost}."""
    return ask_model(
        prompt=prompt,
        model=model,
        system=system,
        temperature=temperature,
    )


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
