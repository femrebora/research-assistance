"""Read/write helper for the in-browser Settings page.

Two classes of configuration:

* **Secrets** (API keys, Zotero key, Flask secret) — reported only as
  configured / not-set. Never echoed to the browser, never written from it.
* **Editable** (paths, CLI commands, timeouts) — surfaced with their current
  value and written back to the ``.env`` file on save.

Writes are surgical: only allow-listed editable keys are touched, existing
lines (comments, blanks, and every secret) are preserved in place.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import find_dotenv

# Reported as configured/not-set only — never editable or echoed.
SECRET_KEYS: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "GEMINI_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "ZOTERO_API_KEY",
    "SEMANTIC_SCHOLAR_API_KEY",
    "ELICIT_API_KEY",
    "FLASK_SECRET_KEY",
)


@dataclass(frozen=True)
class EditableField:
    """A non-secret config key the user may edit from the browser."""

    key: str
    label: str
    group: str
    default: str = ""
    kind: str = "text"  # "text" | "number"
    help: str = ""


# Order here is the order rendered on the page.
EDITABLE_FIELDS: tuple[EditableField, ...] = (
    EditableField("THESIS_ROOT", "Thesis root", "Paths", str(Path.home() / "thesis"),
                  help="Where logs, sessions, and the index live."),
    EditableField("ZOTERO_STORAGE", "Zotero storage", "Paths", "",
                  help="Path to your Zotero/storage folder (PDF attachments)."),
    EditableField("ZOTERO_USER_ID", "Zotero user ID", "Paths", "",
                  help="Numeric user ID from zotero.org/settings/keys."),
    EditableField("CLAUDE_CLI_CMD", "Claude CLI command", "CLI providers", "claude -p"),
    EditableField("GEMINI_CLI_CMD", "Gemini CLI command", "CLI providers", "gemini -p"),
    EditableField("CODEX_CLI_CMD", "Codex CLI command", "CLI providers", "codex exec"),
    EditableField("OLLAMA_CLI_CMD", "Ollama CLI command", "CLI providers", "ollama run llama3.3"),
    EditableField("OLLAMA_MODEL", "Ollama model (API)", "CLI providers", "ollama/llama3.3",
                  help="Model string used by the LiteLLM-managed `local` alias."),
    EditableField("CLI_TIMEOUT", "CLI timeout (seconds)", "CLI providers", "600", kind="number"),
    EditableField("EDITOR", "Editor", "Misc", "",
                  help="Used by interactive review loops (paraphrase/critic)."),
)

EDITABLE_KEYS: frozenset[str] = frozenset(f.key for f in EDITABLE_FIELDS)


def env_path() -> Path:
    """Resolve the .env file to read/write.

    Override with ``RA_ENV_FILE``; otherwise use the nearest existing .env;
    otherwise default to ``.env`` in the current working directory.
    """
    override = os.getenv("RA_ENV_FILE", "").strip()
    if override:
        return Path(override)
    found = find_dotenv(usecwd=True)
    return Path(found) if found else Path.cwd() / ".env"


def secret_status() -> list[dict]:
    """Report which secret keys are configured, without revealing any value."""
    return [
        {"key": key, "configured": bool(os.getenv(key, "").strip())}
        for key in SECRET_KEYS
    ]


def editable_values() -> list[dict]:
    """Current value (or default) for each editable field, grouped for display."""
    out: list[dict] = []
    for f in EDITABLE_FIELDS:
        out.append(
            {
                "key": f.key,
                "label": f.label,
                "group": f.group,
                "kind": f.kind,
                "help": f.help,
                "value": os.getenv(f.key, "") or "",
                "placeholder": f.default,
            }
        )
    return out


def _format_value(value: str) -> str:
    """Quote a .env value when it contains characters that need protection."""
    if value == "" or all(c not in value for c in ' \t#"\''):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def validate(updates: dict[str, str]) -> dict[str, str]:
    """Validate + normalise editable updates. Returns the clean subset to write.

    Rejects any non-editable key (defends against secret writes) and validates
    numeric fields. Raises ValueError on bad input.
    """
    numeric_keys = {f.key for f in EDITABLE_FIELDS if f.kind == "number"}
    clean: dict[str, str] = {}
    for key, raw in updates.items():
        if key not in EDITABLE_KEYS:
            continue  # silently ignore anything not allow-listed (e.g. secrets)
        value = (raw or "").strip()
        if key in numeric_keys and value and not value.isdigit():
            raise ValueError(f"{key} must be a whole number of seconds.")
        clean[key] = value
    return clean


def save(updates: dict[str, str]) -> Path:
    """Write validated editable updates back to .env, preserving all other lines.

    Updates the value of existing allow-listed keys in place; appends new keys
    at the end. Secret lines and comments are never altered. Also reflects the
    change into the current process environment so the UI shows it immediately.
    """
    clean = validate(updates)
    path = env_path()

    lines: list[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()

    seen: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            existing_key = stripped.split("=", 1)[0].strip()
            if existing_key in clean:
                new_lines.append(f"{existing_key}={_format_value(clean[existing_key])}")
                seen.add(existing_key)
                continue
        new_lines.append(line)

    appended = [k for k in clean if k not in seen]
    if appended:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        for key in appended:
            new_lines.append(f"{key}={_format_value(clean[key])}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # Reflect immediately so the page re-renders with the saved values.
    for key, value in clean.items():
        os.environ[key] = value

    return path
