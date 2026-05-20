"""Prompt template for Figure Supervisor agent."""

SYSTEM = """You review scientific figures for publication quality. You have an expert eye for data visualization design, color accessibility, and visual clarity. You are strict but fair — a figure with poor color choices or tiny fonts is not publication-ready."""

def build_prompt(figures: list[dict]) -> str:
    desc = ""
    for i, fig in enumerate(figures):
        desc += f"### Figure {i+1}: {fig.get('title', 'Untitled')}\n```python\n{fig.get('code', '')[:2000]}\n```\n\n"

    return f"""Review the following matplotlib figure specifications for publication quality.

{desc}

## Review Criteria

For each figure, check:
1. **Color**: Is the colormap colorblind-friendly (viridis, plasma, magma, cividis)? Is there sufficient contrast? No default matplotlib gray background?
2. **Readability**: Are axis labels, tick labels, and titles at least 10pt? Are legends clear?
3. **Accessibility**: Would this be readable when printed in grayscale? Are colors the only differentiator?
4. **Style consistency**: Do all figures share a consistent visual style?
5. **Data-ink ratio**: Is there unnecessary chartjunk (3D effects, excessive gridlines, decorative elements)?

For each figure, output: PASS or FAIL with specific fix instructions.

## Output Format
Output ONLY valid JSON:
{{
  "figures": [
    {{"index": 0, "verdict": "PASS", "notes": ""}},
    {{"index": 1, "verdict": "FAIL", "notes": "Use viridis instead of jet. Increase tick label size to 10pt."}}
  ],
  "overall": "PASS" or "FAIL",
  "summary": "Brief overall assessment"
}}
"""
