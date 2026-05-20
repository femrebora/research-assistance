"""Code Analyst agent — Gemini analyzes codebase → technical report."""
from __future__ import annotations

import os
from pathlib import Path

from agentic.bridge import call_agent
from agentic.prompts.code_analyst import SYSTEM, build_prompt


def run_code_analyst(state: dict) -> dict:
    """Analyze user's codebase and produce a technical report."""
    code_path = state["code_path"]

    file_list_lines = []
    key_contents = []
    MAX_FILES = 30
    MAX_SIZE = 8000

    for root, dirs, files in os.walk(code_path):
        dirs[:] = [d for d in dirs if not d.startswith((".", "__")) and d not in ("node_modules", "venv", ".venv", "build", "dist")]
        for f in files:
            if f.startswith("."):
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, code_path)
            file_list_lines.append(rel)
            if len(key_contents) < MAX_FILES and os.path.getsize(full) < 50000:
                try:
                    content = Path(full).read_text(encoding="utf-8", errors="replace")
                    key_contents.append(f"### {rel}\n```\n{content[:MAX_SIZE]}{'...' if len(content) > MAX_SIZE else ''}\n```")
                except Exception:
                    pass

    prompt = build_prompt(
        code_summary=state["user_summary"],
        file_list="\n".join(file_list_lines[:200]),
        key_files_content="\n\n".join(key_contents[:MAX_FILES]),
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
