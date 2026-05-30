"""Prompt template for Figure Generator agent."""

SYSTEM = """You generate publication-quality matplotlib/seaborn visualization code that WILL be executed to render PNG files.

Your code MUST be:
- Complete and runnable (all imports included, no external data files)
- Syntactically correct — it will be run through `python` with no user intervention
- Uses colorblind-friendly palettes (viridis, plasma, magma, cividis)
- Has readable font sizes (>= 10pt)
- Uses dark background or clean white background (NEVER default matplotlib gray)
- Includes proper axis labels and titles
- Saves output as high-resolution PNG (dpi=300) to the EXACT path specified
- Creates the output directory with os.makedirs() before saving

You are generating figures for a REVIEW ARTICLE. Use realistic-looking synthetic data."""

def build_prompt(
    technical_report: str,
    code_path: str,
    figure_descriptions: str,
    output_dir: str,
) -> str:
    return f"""Generate matplotlib/seaborn Python code for the review-article figures described below.

Each figure script WILL be executed independently to render a PNG. Code must be complete, correct, and run without errors — no external data files, no user input.

## Technical Context
{technical_report[:3000]}

## Code Location
{code_path}

## Requested Figures
{figure_descriptions}

## Output Directory
Save ALL figures to this directory: {output_dir}

Use these exact save paths (one per figure):
  Figure 1 -> {output_dir}/figure_1.png
  Figure 2 -> {output_dir}/figure_2.png
  Figure 3 -> {output_dir}/figure_3.png
  Figure 4 -> {output_dir}/figure_4.png

Include `os.makedirs("{output_dir}", exist_ok=True)` before saving.

## Requirements
For each figure, output a COMPLETE, RUNNABLE Python script. Each script must:
1. Import matplotlib, seaborn, numpy, and os
2. Use 'viridis' or 'plasma' colormap (colorblind-friendly)
3. Set font sizes to at least 10pt
4. Use `plt.style.use('dark_background')` for a professional look
5. Create the output directory with `os.makedirs("{output_dir}", exist_ok=True)`
6. Save to the EXACT path shown above: `plt.savefig(path, dpi=300, bbox_inches='tight')`
7. Include proper axis labels, title, and legend
8. Generate realistic-looking synthetic data inline (no external files)

## Output Format
Output each script in a clearly labeled code block:

### Figure 1: [descriptive name for review article]
```python
[complete script with imports, inline synthetic data, and plt.savefig to {output_dir}/figure_1.png]
```

### Figure 2: [descriptive name]
```python
[complete script — save to {output_dir}/figure_2.png]
```

### Figure 3: [descriptive name]
```python
[complete script — save to {output_dir}/figure_3.png]
```

### Figure 4: [descriptive name]
```python
[complete script — save to {output_dir}/figure_4.png]
```"""
