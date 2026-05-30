"""Figure Generator agent — Gemini creates matplotlib visualization code, rendered to PNG."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from agentic.bridge import call_agent
from agentic.prompts.figure_gen import SYSTEM, build_prompt

_FIGURE_TIMEOUT = 60  # seconds per figure render


def _execute_figure(code: str, figures_dir: Path, expected_path: Path) -> str | None:
    """Write figure code to a temp file, execute it, and return the PNG path or None."""
    import time
    start_time = time.time()
    # Prepend directory creation so the script always works
    full_code = (
        f"import os\n"
        f"os.makedirs({str(figures_dir)!r}, exist_ok=True)\n\n"
        f"{code}"
    )

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False, dir=str(figures_dir),
        ) as f:
            f.write(full_code)
            tmp_path = f.name

        proc = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=_FIGURE_TIMEOUT,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.strip()[:600]
            print(f"  [Figure Gen] execution failed (exit {proc.returncode}): {stderr}",
                  file=sys.stderr, flush=True)
    except subprocess.TimeoutExpired:
        print(f"  [Figure Gen] execution timed out ({_FIGURE_TIMEOUT}s)",
              file=sys.stderr, flush=True)
    except Exception as e:
        print(f"  [Figure Gen] execution error: {e}", file=sys.stderr, flush=True)
    finally:
        if tmp_path is not None and os.path.isfile(tmp_path):
            os.unlink(tmp_path)

    # Check expected path first, then scan for any new PNG
    if expected_path.is_file():
        return str(expected_path)

    # Fallback: find any PNG in the figures dir created during this execution
    pngs = [p for p in figures_dir.glob("*.png") if p.stat().st_mtime >= start_time]
    if pngs:
        pngs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return str(pngs[0])
    return None


def run_figure_gen(state: dict) -> dict:
    """Generate matplotlib figures from technical context and render them to PNG."""
    output_dir = state.get("output_dir")
    if not output_dir:
        print("  [Figure Gen] WARNING: no output_dir in state, figures won't render",
              file=sys.stderr, flush=True)
        return _empty_result()

    figures_dir = Path(output_dir) / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    figure_descriptions = state.get(
        "figure_descriptions",
        "Generate 3 to 4 figures appropriate for a review article on personalized medicine "
        "based on the technical report. "
        "Include: "
        "1) A bar chart comparing market sizes or adoption rates across key sectors, "
        "2) A timeline of major breakthroughs or regulatory milestones, "
        "3) A bubble chart or scatter plot showing the company/institution landscape "
        "(e.g., x-axis = therapy area, y-axis = maturity stage, bubble size = funding), "
        "4) A comparison table or heatmap of technologies, platforms, or approaches.",
    )

    prompt = build_prompt(
        technical_report=state.get("technical_report", ""),
        code_path=state.get("code_path", ""),
        figure_descriptions=figure_descriptions,
        output_dir=str(figures_dir),
    )

    result = call_agent(prompt=prompt, model="gemini", system=SYSTEM, temperature=0.3)

    text = result["text"]
    figure_blocks = re.findall(r"###\s*(Figure \d+:.*?)\n```python\n(.*?)```", text, re.DOTALL)

    figures = []
    for i, (title, code) in enumerate(figure_blocks):
        expected_path = figures_dir / f"figure_{i+1}.png"
        png_path = _execute_figure(code.strip(), figures_dir, expected_path)

        figures.append({
            "title": title.strip(),
            "code": code.strip(),
            "png_path": png_path,
            "review": None,
        })

    if not figures:
        figures = [{"title": "figures", "code": text, "png_path": None, "review": None}]

    return {
        "figures": figures,
        "agent_calls": [{
            "agent": "figure_gen",
            "model": "gemini",
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "cost": result["cost"],
        }],
    }


def _empty_result() -> dict:
    return {
        "figures": [],
        "agent_calls": [{
            "agent": "figure_gen",
            "model": "gemini",
            "input_tokens": None,
            "output_tokens": None,
            "cost": None,
        }],
    }
