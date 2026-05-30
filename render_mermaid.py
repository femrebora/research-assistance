#!/usr/bin/env python3
"""render_mermaid.py — render Mermaid diagrams in a markdown file to PNG.

Extracts ```mermaid code blocks, renders each to PNG via mmdc (mermaid-cli),
and saves them alongside the markdown file.

Usage:
    ./render_mermaid.py paper.md              # renders to paper_figures/
    ./render_mermaid.py paper.md --inline      # replaces mermaid blocks with <img> tags
    ./render_mermaid.py paper.md --output-dir figs
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import click

MERMAID_BLOCK = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)


def extract_blocks(text: str) -> list[tuple[int, str]]:
    """Find all ```mermaid blocks. Returns [(index, content), ...]."""
    return [(i, m.group(1).strip()) for i, m in enumerate(MERMAID_BLOCK.finditer(text))]


def render_block(mermaid_content: str, output_path: Path, scale: int = 2) -> bool:
    """Render a single Mermaid diagram to PNG. Returns True on success."""
    # Write mermaid source to temp file
    tmp_mmd = output_path.with_suffix(".mmd")
    tmp_mmd.write_text(mermaid_content, encoding="utf-8")

    try:
        result = subprocess.run(
            [
                "mmdc",
                "-i", str(tmp_mmd),
                "-o", str(output_path),
                "-s", str(scale),
                "-b", "transparent",
                "--pdfFit",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        tmp_mmd.unlink(missing_ok=True)
        return result.returncode == 0 and output_path.exists()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        tmp_mmd.unlink(missing_ok=True)
        print(f"  [WARN] mmdc failed: {e}", file=sys.stderr)
        return False


def render_all(paper_path: Path, output_dir: Path, scale: int = 2) -> list[Path]:
    """Render all Mermaid diagrams in a markdown file to PNGs."""
    text = paper_path.read_text(encoding="utf-8")
    blocks = extract_blocks(text)

    if not blocks:
        print("No Mermaid blocks found.")
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = []

    for i, content in blocks:
        # Extract a title from the content (first non-empty, non-%% line)
        lines = [line.strip() for line in content.splitlines()
                 if line.strip() and not line.strip().startswith("%%")]
        title_line = next((line for line in lines if line.lower().startswith("title")), None)
        title = re.sub(r"^title\s*:?\s*", "", title_line, flags=re.IGNORECASE).strip() if title_line else f"figure_{i+1}"
        # Clean title for filename
        safe_title = re.sub(r"[^a-zA-Z0-9_-]", "_", title)[:40]

        out_path = output_dir / f"figure_{i+1:02d}_{safe_title}.png"
        print(f"  Rendering figure {i+1}...", file=sys.stderr)

        if render_block(content, out_path, scale):
            rendered.append(out_path)
            print(f"    → {out_path}", file=sys.stderr)
        else:
            print(f"    ✗ Failed to render figure {i+1}", file=sys.stderr)

    return rendered


def inline_images(text: str, figure_dir: str, rendered: list[Path]) -> str:
    """Replace ```mermaid blocks with <img> tags pointing to rendered PNGs."""
    paths_iter = iter(rendered)

    def _replace(m):
        try:
            p = next(paths_iter)
            return f'<img src="{figure_dir}/{p.name}" alt="Figure" style="max-width:100%">\n\n*Figure: see {p.name}*'
        except StopIteration:
            return m.group(0)

    return MERMAID_BLOCK.sub(_replace, text)


@click.command()
@click.argument("paper", type=click.Path(exists=True))
@click.option("--output-dir", "-o", default=None, help="Directory for PNG files.")
@click.option("--inline", is_flag=True, help="Replace mermaid blocks with <img> tags.")
@click.option("--scale", "-s", default=2, type=int, help="PNG scale factor (default: 2).")
def main(paper, output_dir, inline, scale):
    """Render Mermaid diagrams in a markdown file to PNG."""
    paper_path = Path(paper).resolve()

    fig_dir = Path(output_dir) if output_dir else paper_path.parent / f"{paper_path.stem}_figures"

    print(f"Paper: {paper_path}")
    print(f"Figures: {fig_dir}\n")

    rendered = render_all(paper_path, fig_dir, scale)

    if not rendered:
        print("\nNo diagrams rendered.")
        return

    print(f"\n{len(rendered)} diagrams rendered to {fig_dir}/")

    if inline:
        text = paper_path.read_text(encoding="utf-8")
        rel_dir = fig_dir.name
        new_text = inline_images(text, rel_dir, rendered)

        backup = paper_path.with_suffix(".md.bak")
        paper_path.rename(backup)
        paper_path.write_text(new_text, encoding="utf-8")
        print(f"  Updated {paper_path} with <img> tags (backup: {backup})")


if __name__ == "__main__":
    main()
