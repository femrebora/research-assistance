"""Code Analyst agent — Gemini analyzes codebase → technical report."""
from __future__ import annotations

import os
from pathlib import Path

from agentic.bridge import call_agent
from agentic.prompts.code_analyst import SYSTEM, build_prompt

MAX_KEY_FILES = 4
MAX_SIZE_PER_FILE = 1500
MAX_TOTAL_PROMPT = 20000  # stay well under shell ARG_MAX


def _is_important(fname: str) -> bool:
    """Prioritize meaningful source files over Config/tests/data."""
    low = fname.lower()
    if low.endswith((".py", ".md", ".rst", ".txt")):
        return not any(x in low for x in ("test_", "conftest", "__pycache__"))
    return False


def run_code_analyst(state: dict) -> dict:
    """Analyze user's codebase and produce a technical report."""
    code_path = state["code_path"]

    all_files = []
    for root, dirs, files in os.walk(code_path):
        dirs[:] = [d for d in dirs
                   if not d.startswith((".", "__"))
                   and d not in ("node_modules", "venv", ".venv", "build", "dist",
                                 "results", "uploads", "logs", "test_output")]
        for f in files:
            if f.startswith("."):
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, code_path)
            try:
                sz = os.path.getsize(full)
            except OSError:
                sz = 0
            all_files.append((rel, full, sz))

    file_list_lines = [rel for rel, _, _ in all_files]

    # Prefer important files, then by size (largest first, but under 100KB)
    important = [(rel, p, s) for rel, p, s in all_files if _is_important(rel) and s < 100000]
    important.sort(key=lambda x: -x[2])

    key_contents = []
    total_prompt_size = 0
    for rel, full, _sz in important:
        if len(key_contents) >= MAX_KEY_FILES:
            break
        try:
            content = Path(full).read_text(encoding="utf-8", errors="replace")
            snippet = content[:MAX_SIZE_PER_FILE]
            block = f"### {rel}\n```\n{snippet}{'...' if len(content) > MAX_SIZE_PER_FILE else ''}\n```"
            if total_prompt_size + len(block) > MAX_TOTAL_PROMPT:
                break
            key_contents.append(block)
            total_prompt_size += len(block)
        except Exception:
            pass

    prompt = build_prompt(
        code_summary=state["user_summary"],
        file_list="\n".join(file_list_lines[:150]),
        key_files_content="\n\n".join(key_contents),
    )

    result = call_agent(prompt=prompt, model="gemini", system=SYSTEM)

    return {
        "technical_report": result["text"],
        "agent_calls": [{
            "agent": "code_analyst",
            "model": "gemini",
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "cost": result["cost"],
        }],
    }
