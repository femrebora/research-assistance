"""Provider introspection for the web UI.

Reports the health of both API-keyed model providers (Anthropic, Gemini,
DeepSeek, OpenAI) and CLI-routed providers (claude-cli, gemini-cli, codex-cli,
ollama-cli), and runs a lightweight round-trip test against any model alias.

Secrets are never returned in full — API keys are reported only as
configured/not-set, never echoed.
"""
from __future__ import annotations

import os
import shlex
import shutil
import time
from dataclasses import dataclass

from research_assistant.common import CLI_PROVIDERS, MODELS, ask_model

# Which env var holds the key for each API-backed alias, grouped by provider.
# (alias list is informational; the env var is what gates availability.)
API_PROVIDERS: tuple[dict, ...] = (
    {
        "name": "Anthropic (Claude)",
        "env_var": "ANTHROPIC_API_KEY",
        "aliases": ("claude", "sonnet", "haiku"),
    },
    {
        "name": "Google (Gemini)",
        "env_var": "GEMINI_API_KEY",
        "aliases": ("gemini", "flash"),
    },
    {
        "name": "DeepSeek",
        "env_var": "DEEPSEEK_API_KEY",
        "aliases": ("deepseek",),
    },
    {
        "name": "OpenAI (GPT)",
        "env_var": "OPENAI_API_KEY",
        "aliases": ("gpt", "gpt-mini", "codex"),
    },
)


@dataclass(frozen=True)
class CliStatus:
    """Resolved state of a single CLI-routed provider."""

    alias: str
    command: str
    binary: str
    found: bool
    path: str | None


@dataclass(frozen=True)
class ApiStatus:
    """Configuration state of a single API-keyed provider (never the key itself)."""

    name: str
    env_var: str
    aliases: tuple[str, ...]
    configured: bool


def cli_provider_status() -> list[CliStatus]:
    """Resolve each CLI-routed alias to a binary and report whether it is installed."""
    statuses: list[CliStatus] = []
    for alias, command in CLI_PROVIDERS.items():
        parts = shlex.split(command)
        binary = parts[0] if parts else ""
        path = shutil.which(binary) if binary else None
        statuses.append(
            CliStatus(
                alias=alias,
                command=command,
                binary=binary,
                found=path is not None,
                path=path,
            )
        )
    return statuses


def api_provider_status() -> list[ApiStatus]:
    """Report which API providers have a key configured (without revealing it)."""
    return [
        ApiStatus(
            name=p["name"],
            env_var=p["env_var"],
            aliases=p["aliases"],
            configured=bool(os.getenv(p["env_var"], "").strip()),
        )
        for p in API_PROVIDERS
    ]


def test_provider(alias: str, prompt: str = "Reply with the single word: OK.") -> dict:
    """Run a tiny prompt through `alias` and report success, latency, and a snippet.

    Returns a dict safe to render directly: never contains secrets. On failure,
    `ok` is False and `error` carries a short message.
    """
    if alias not in MODELS:
        return {"ok": False, "alias": alias, "error": f"Unknown model alias '{alias}'."}

    start = time.monotonic()
    try:
        result = ask_model(prompt, model=alias, max_tokens=16, temperature=0.0)
    except Exception as e:  # surface any provider error to the UI
        return {
            "ok": False,
            "alias": alias,
            "elapsed_ms": int((time.monotonic() - start) * 1000),
            "error": str(e)[:400],
        }

    elapsed_ms = int((time.monotonic() - start) * 1000)
    text = (result.get("text") or "").strip()
    # CLI/API error paths return a parenthetical "(error: ...)" sentinel as text.
    ok = bool(text) and not text.startswith("(error")
    return {
        "ok": ok,
        "alias": alias,
        "elapsed_ms": elapsed_ms,
        "snippet": text[:200],
        "error": None if ok else (text[:400] or "Empty response."),
    }
