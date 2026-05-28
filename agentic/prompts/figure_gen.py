"""Prompt template for Figure Generator agent."""

SYSTEM = """You generate publication-quality matplotlib/seaborn visualization code. Your code is:
- Complete and runnable (all imports included)
- Uses colorblind-friendly palettes
- Has readable font sizes (≥10pt)
- Uses dark background or clean white background (NEVER default matplotlib gray)
- Includes proper axis labels and titles
- Saves output as high-resolution PNG"""

def build_prompt(technical_report: str, code_path: str, figure_descriptions: str) -> str:
    return f"""Generate matplotlib/seaborn Python code for the figures described below.

## Technical Context
{technical_report[:3000]}

## Code Location
{code_path}

## Requested Figures
{figure_descriptions}

## Output
For each figure, output a COMPLETE, RUNNABLE Python script. Each script must:
1. Import matplotlib + seaborn (and numpy/pandas if needed)
2. Use the 'viridis' or 'plasma' colormap (colorblind-friendly)
3. Set font sizes to at least 10pt
4. Use `plt.style.use('dark_background')` for a professional look
5. Save to the output path with `plt.savefig(path, dpi=300, bbox_inches='tight')`
6. Include proper axis labels, title, and legend if applicable

Output each script in a clearly labeled code block:

### Figure 1: [name]
```python
[complete script]
```

### Figure 2: [name]
```python
[complete script]
```"""
