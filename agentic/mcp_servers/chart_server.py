#!/usr/bin/env python3
"""Chart MCP Server — publication-quality chart generation for pipeline agents.

Provides 8 chart types with scientific styling. Agents pass structured JSON
data and get back rendered PNG files. No matplotlib knowledge needed.

Chart types:
  bar         — simple vertical bar chart
  grouped_bar — multi-series grouped/comparison bars
  line        — trend/time series with optional markers
  scatter     — scatter/bubble plot
  heatmap     — matrix comparison with annotations
  timeline    — horizontal milestone chronology
  pie         — market share / segmentation
  radar       — multi-dimensional comparison (spider chart)

Run: python agentic/mcp_servers/chart_server.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("PaperForge Charts")

# ── Styling ───────────────────────────────────────────────────────────────

THEMES = {
    "scientific": {
        "bg": "white", "figsize": (10, 6), "dpi": 300,
        "title_size": 14, "label_size": 12, "tick_size": 10,
        "grid": False, "spines": "left_bottom",
        "font": "DejaVu Sans",
    },
    "presentation": {
        "bg": "white", "figsize": (12, 7), "dpi": 200,
        "title_size": 18, "label_size": 14, "tick_size": 12,
        "grid": True, "spines": "all",
        "font": "DejaVu Sans",
    },
    "web": {
        "bg": "white", "figsize": (8, 5), "dpi": 150,
        "title_size": 13, "label_size": 11, "tick_size": 9,
        "grid": False, "spines": "left_bottom",
        "font": "DejaVu Sans",
    },
}

PALETTES = {
    "muted": ["#2166ac","#b2182b","#4daf4a","#ff7f00","#984ea3","#00a896","#f4a261","#e76f51"],
    "viridis": plt.cm.viridis,
    "plasma": plt.cm.plasma,
    "coolwarm": plt.cm.coolwarm,
    "blues": plt.cm.Blues,
    "greens": plt.cm.Greens,
    "oranges": plt.cm.Oranges,
    "rdbu": plt.cm.RdBu,
}


def _apply_theme(theme_name: str = "scientific"):
    """Apply a pre-built theme to matplotlib."""
    theme = THEMES.get(theme_name, THEMES["scientific"])
    plt.rcParams.update({
        "font.family": theme["font"],
        "font.size": theme["tick_size"],
        "axes.titlesize": theme["title_size"],
        "axes.labelsize": theme["label_size"],
        "xtick.labelsize": theme["tick_size"],
        "ytick.labelsize": theme["tick_size"],
        "figure.facecolor": theme["bg"],
        "axes.facecolor": theme["bg"],
        "axes.grid": theme["grid"],
        "grid.alpha": 0.3,
        "grid.linestyle": "--",
        "axes.spines.top": theme["spines"] != "left_bottom",
        "axes.spines.right": theme["spines"] != "left_bottom",
    })


def _get_colors(palette: str, n: int) -> list:
    """Get n colors from a palette."""
    p = PALETTES.get(palette, PALETTES["muted"])
    if isinstance(p, list):
        return (p * (n // len(p) + 1))[:n]
    return [p(i / max(n-1, 1)) for i in range(n)]


def _finalize(fig, ax, output: str, theme_name: str) -> str:
    """Save figure with tight layout. Returns output path."""
    theme = THEMES.get(theme_name, THEMES["scientific"])

    # Force draw to populate tick labels, then handle long labels
    fig.canvas.draw()
    labels = [t.get_text() for t in ax.get_xticklabels()]
    max_label_len = max((len(label) for label in labels), default=0)
    if max_label_len > 30:
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=theme["tick_size"] - 2)
    elif max_label_len > 15:
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=theme["tick_size"] - 1)

    fig.tight_layout(pad=1.5)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=theme["dpi"], bbox_inches="tight", facecolor=theme["bg"])
    plt.close(fig)
    return output


def _validate_bar_data(data: dict) -> tuple[list, list]:
    """Extract and validate categories + values from bar data. Raises on bad input."""
    categories = data.get("categories", [])
    values = data.get("values", [])
    if not categories or not values:
        raise ValueError("categories and values are required (must be non-empty lists)")
    if len(categories) != len(values):
        raise ValueError(f"categories ({len(categories)}) and values ({len(values)}) must have same length")
    if not all(isinstance(v, (int, float)) for v in values):
        raise ValueError("all values must be numbers")
    return categories, values


# ── MCP Tools ─────────────────────────────────────────────────────────────

@mcp.tool()
def bar_chart(
    data_json: str,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    output: str = "chart.png",
    theme: str = "scientific",
    palette: str = "muted",
    horizontal: bool = False,
) -> str:
    """Create a bar chart from categories and values.

    Args:
        data_json: JSON string like {"categories":["A","B","C"], "values":[10,20,15]}
        title: Chart title (optional)
        xlabel: X-axis label
        ylabel: Y-axis label
        output: File path for PNG output (default: chart.png)
        theme: "scientific", "presentation", or "web"
        palette: Color palette name ("muted","viridis","plasma","blues","greens","oranges")
        horizontal: If true, creates a horizontal bar chart

    Returns path to rendered PNG on success.

    Example:
        bar_chart('{"categories":["Genomics","Proteomics","CDx"],"values":[22,8,16]}',
                   title="Market Size", ylabel="USD Billions")
    """
    try:
        data = json.loads(data_json)
        categories, values = _validate_bar_data(data)
    except (json.JSONDecodeError, ValueError) as e:
        return f"Error: {e}"

    _apply_theme(theme)
    colors = _get_colors(palette, len(categories))
    t = THEMES.get(theme, THEMES["scientific"])

    fig, ax = plt.subplots(figsize=t["figsize"])

    if horizontal:
        bars = ax.barh(categories, values, color=colors, edgecolor="white", linewidth=0.8, height=0.65)
        ax.invert_yaxis()
        for bar, val in zip(bars, values, strict=True):
            ax.text(bar.get_width() + max(values)*0.01, bar.get_y() + bar.get_height()/2,
                    str(val), va="center", fontsize=t["tick_size"], fontweight="bold")
    else:
        bars = ax.bar(categories, values, color=colors, edgecolor="white", linewidth=0.8, width=0.65)
        for bar, val in zip(bars, values, strict=True):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.01,
                    str(val), ha="center", fontsize=t["tick_size"], fontweight="bold")

    ax.set_title(title, fontweight="bold", pad=15) if title else None
    ax.set_xlabel(xlabel) if xlabel else None
    ax.set_ylabel(ylabel) if ylabel else None

    return _finalize(fig, ax, output, theme)


@mcp.tool()
def grouped_bar_chart(
    data_json: str,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    output: str = "chart.png",
    theme: str = "scientific",
    palette: str = "muted",
) -> str:
    """Create a grouped/compared bar chart with multiple series.

    Args:
        data_json: JSON like {"categories":["A","B"], "series":{"2024":[10,20],"2025":[15,25]}}
        title: Chart title
        xlabel: X-axis label
        ylabel: Y-axis label
        output: File path for PNG
        theme: "scientific", "presentation", or "web"
        palette: Color palette name

    Returns path to rendered PNG.

    Example:
        grouped_bar_chart('{"categories":["Genomics","Proteomics","CDx"],
                            "series":{"2024":[12,5,8],"2026":[22,8,16]}}',
                           title="Market Growth", ylabel="USD Billions")
    """
    try:
        data = json.loads(data_json)
        categories = data.get("categories", [])
        series = data.get("series", {})
        if not categories or not series:
            return "Error: categories and series are required"
        if not all(len(v) == len(categories) for v in series.values()):
            return "Error: each series must have same length as categories"
    except json.JSONDecodeError as e:
        return f"Error: invalid JSON — {e}"

    _apply_theme(theme)
    t = THEMES.get(theme, THEMES["scientific"])
    series_names = list(series.keys())
    colors = _get_colors(palette, len(series_names))

    fig, ax = plt.subplots(figsize=t["figsize"])
    x = np.arange(len(categories))
    n_series = len(series_names)
    width = 0.75 / max(n_series, 1)
    bar_width = width * 0.85

    for i, (name, vals) in enumerate(series.items()):
        offset = (i - (n_series-1)/2) * width
        bars = ax.bar(x + offset, vals, bar_width, label=name,
                       color=colors[i], edgecolor="white", linewidth=0.5)
        for bar, val in zip(bars, vals, strict=True):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(
                    max(vs) for vs in series.values())*0.01,
                    str(val), ha="center", fontsize=t["tick_size"]-1, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_title(title, fontweight="bold", pad=15) if title else None
    ax.set_xlabel(xlabel) if xlabel else None
    ax.set_ylabel(ylabel) if ylabel else None
    if len(series_names) > 1:
        ax.legend(frameon=False, fontsize=t["tick_size"]-1)

    return _finalize(fig, ax, output, theme)


@mcp.tool()
def line_chart(
    data_json: str,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    output: str = "chart.png",
    theme: str = "scientific",
    palette: str = "muted",
) -> str:
    """Create a line/trend chart, optionally with multiple series.

    Args:
        data_json: JSON like {"x":[2020,2021,2022,2023,2024,2025,2026],
                              "series":{"Market A":[10,12,15,18,22,28,35],
                                        "Market B":[5,6,8,10,14,19,25]}}
                   Or simple: {"x":[1,2,3,4], "y":[10,20,15,25]}
        title: Chart title
        xlabel: X-axis label
        ylabel: Y-axis label
        output: File path for PNG
        theme: "scientific", "presentation", or "web"
        palette: Color palette name

    Returns path to rendered PNG.

    Example:
        line_chart('{"x":[2020,2022,2024,2026],"series":{"PM Market":[12,16,22,28]}}',
                    title="Market Growth", ylabel="USD Billions")
    """
    try:
        data = json.loads(data_json)
        x = data.get("x", [])
        if "series" in data:
            series = data["series"]
        elif "y" in data:
            series = {"": data["y"]}
        else:
            return "Error: provide 'series' (multi-line) or 'y' (single line)"
    except json.JSONDecodeError as e:
        return f"Error: invalid JSON — {e}"

    if not x:
        return "Error: x values required"

    _apply_theme(theme)
    t = THEMES.get(theme, THEMES["scientific"])
    series_names = list(series.keys())
    colors = _get_colors(palette, len(series_names))
    markers = ["o","s","^","D","v","p","*","h"]

    fig, ax = plt.subplots(figsize=t["figsize"])

    for i, (name, vals) in enumerate(series.items()):
        if len(vals) != len(x):
            return f"Error: series '{name}' length ({len(vals)}) != x length ({len(x)})"
        ax.plot(x, vals, color=colors[i], marker=markers[i % len(markers)],
                markersize=6, linewidth=2.2, label=name if name else None)

    ax.set_title(title, fontweight="bold", pad=15) if title else None
    ax.set_xlabel(xlabel) if xlabel else None
    ax.set_ylabel(ylabel) if ylabel else None
    if any(s for s in series_names if s):
        ax.legend(frameon=False, fontsize=t["tick_size"]-1)

    # Integer x-axis if all x values are integers
    if all(isinstance(v, (int, float)) and v == int(v) for v in x):
        ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    return _finalize(fig, ax, output, theme)


@mcp.tool()
def scatter_chart(
    data_json: str,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    output: str = "chart.png",
    theme: str = "scientific",
    palette: str = "muted",
) -> str:
    """Create a scatter or bubble chart.

    Args:
        data_json: JSON like {"series":[{"x":[1,2,3],"y":[10,20,15],"sizes":[50,100,80],"label":"Series A"}]}
                   Sizes are optional (creates bubble chart if provided).
        title: Chart title
        xlabel: X-axis ("Funding, USD M")
        ylabel: Y-axis ("Maturity Score")
        output: File path for PNG
        theme/palette: Styling options

    Example (company landscape):
        scatter_chart('{"series":[{"x":[10,25,50],"y":[3,5,8],"sizes":[100,200,500],
                       "labels":["StartupA","StartupB","StartupC"]}]}',
                       xlabel="Funding ($M)", ylabel="Maturity (1-10)")

    Returns path to rendered PNG.
    """
    try:
        data = json.loads(data_json)
        series_list = data.get("series", [data])  # accept single or multiple
    except json.JSONDecodeError as e:
        return f"Error: invalid JSON — {e}"

    _apply_theme(theme)
    t = THEMES.get(theme, THEMES["scientific"])
    colors = _get_colors(palette, len(series_list))

    fig, ax = plt.subplots(figsize=t["figsize"])
    all_x, all_y = [], []

    for i, s in enumerate(series_list):
        xs = s.get("x", [])
        ys = s.get("y", [])
        sizes = s.get("sizes")
        labels = s.get("labels", [])
        name = s.get("label", "")

        if len(xs) != len(ys):
            return f"Error: x and y must have same length in series {i}"

        base_size = 80
        sz = [base_size] * len(xs) if not sizes else [max(20, v*2) for v in sizes]

        ax.scatter(xs, ys, s=sz, c=[colors[i]], alpha=0.75, edgecolors="white",
                    linewidth=0.5, label=name if name else None, zorder=3)

        for j, lbl in enumerate(labels):
            if lbl:
                ax.annotate(lbl, (xs[j], ys[j]), textcoords="offset points",
                            xytext=(0, 10), ha="center", fontsize=t["tick_size"]-2)

        all_x.extend(xs)
        all_y.extend(ys)

    ax.set_title(title, fontweight="bold", pad=15) if title else None
    ax.set_xlabel(xlabel) if xlabel else None
    ax.set_ylabel(ylabel) if ylabel else None

    # Add padding
    if all_x:
        px = (max(all_x) - min(all_x)) * 0.1 or 1
        ax.set_xlim(min(all_x) - px, max(all_x) + px)
    if all_y:
        py = (max(all_y) - min(all_y)) * 0.1 or 1
        ax.set_ylim(min(all_y) - py, max(all_y) + py)

    has_labels = any(s.get("label","") for s in series_list)
    if has_labels:
        ax.legend(frameon=False, fontsize=t["tick_size"]-1)

    return _finalize(fig, ax, output, theme)


@mcp.tool()
def heatmap_chart(
    data_json: str,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    output: str = "chart.png",
    theme: str = "scientific",
    palette: str = "rdbu",
    annotate: bool = True,
) -> str:
    """Create a heatmap for comparing methods/technologies across categories.

    Args:
        data_json: JSON like {"row_labels":["Method A","Method B"],
                              "col_labels":["Accuracy","Speed","Cost"],
                              "data":[[0.9,0.7,0.5],[0.8,0.6,0.4]]}
        title: Chart title
        xlabel, ylabel: Axis labels
        output: File path for PNG
        theme: "scientific", "presentation", or "web"
        palette: "rdbu", "coolwarm", "viridis", "blues", "greens", "oranges"
        annotate: Show values in cells (default true)

    Returns path to rendered PNG.
    """
    try:
        data = json.loads(data_json)
        matrix = data.get("data", [])
        row_labels = data.get("row_labels", [f"R{i}" for i in range(len(matrix))])
        col_labels = data.get("col_labels", [f"C{i}" for i in range(len(matrix[0]) if matrix else 0)])
    except json.JSONDecodeError as e:
        return f"Error: invalid JSON — {e}"

    if not matrix or not matrix[0]:
        return "Error: data must be a non-empty 2D array"

    _apply_theme(theme)
    t = THEMES.get(theme, THEMES["scientific"])

    n_rows, n_cols = len(matrix), len(matrix[0])
    fig, ax = plt.subplots(figsize=(max(8, n_cols*1.5), max(5, n_rows*0.8)))

    cmap = PALETTES.get(palette, PALETTES["rdbu"])
    im = ax.imshow(matrix, cmap=cmap, aspect="auto")

    if annotate:
        for i in range(n_rows):
            for j in range(n_cols):
                val = matrix[i][j]
                rgb = cmap(val)[:3]
                luminance = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
                text_color = "white" if luminance < 0.5 else "black"
                ax.text(j, i, str(val), ha="center", va="center",
                        fontsize=t["tick_size"], fontweight="bold",
                        color=text_color)

    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(col_labels)
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(row_labels)
    ax.set_title(title, fontweight="bold", pad=15) if title else None
    ax.set_xlabel(xlabel) if xlabel else None
    ax.set_ylabel(ylabel) if ylabel else None

    fig.colorbar(im, ax=ax, shrink=0.8)
    return _finalize(fig, ax, output, theme)


@mcp.tool()
def timeline_chart(
    data_json: str,
    title: str = "",
    output: str = "chart.png",
    theme: str = "scientific",
) -> str:
    """Create a horizontal timeline of milestones.

    Args:
        data_json: JSON like {"events":[
            {"date":"2003","label":"Human Genome Project completed"},
            {"date":"2013","label":"First NGS companion diagnostic"}
        ]}
        title: Chart title
        output: File path for PNG
        theme: "scientific", "presentation", or "web"

    Returns path to rendered PNG.
    """
    try:
        data = json.loads(data_json)
        events = data.get("events", [])
        if not events:
            return "Error: events list required"
    except json.JSONDecodeError as e:
        return f"Error: invalid JSON — {e}"

    _apply_theme(theme)
    t = THEMES.get(theme, THEMES["scientific"])
    n = len(events)
    fig, ax = plt.subplots(figsize=(10, max(4, n * 0.9)))

    dates = [e.get("date","?") for e in events]
    labels = [e.get("label","") for e in events]

    ax.set_ylim(-0.8, n - 0.2)

    for i, (date, label) in enumerate(zip(dates, labels, strict=True)):
        # Timeline dot
        ax.plot(0, i, "o", color="#2166ac", markersize=12, zorder=3)
        # Date on left
        ax.text(-0.02, i, date, ha="right", va="center",
                fontsize=t["tick_size"], fontweight="bold", color="#555")
        # Label on right
        ax.text(0.02, i, label, ha="left", va="center",
                fontsize=t["tick_size"], wrap=True)
        # Connector line
        if i < n - 1:
            ax.plot([0, 0], [i + 0.45, i + 0.55], color="#ccc", linewidth=1)

    ax.axvline(0, color="#2166ac", linewidth=2, alpha=0.5)
    ax.axis("off")
    ax.set_xlim(-0.5, 1.5)
    ax.set_title(title, fontweight="bold", pad=15, loc="left") if title else None

    return _finalize(fig, ax, output, theme)


@mcp.tool()
def pie_chart(
    data_json: str,
    title: str = "",
    output: str = "chart.png",
    theme: str = "scientific",
    palette: str = "muted",
) -> str:
    """Create a pie/donut chart for market share or segmentation.

    Args:
        data_json: JSON like {"segments":[
            {"label":"Diagnostics","value":39.6},
            {"label":"Therapeutics","value":35.0},
            {"label":"Digital Health","value":15.8},
            {"label":"Other","value":9.6}
        ]}
        title: Chart title
        output: File path for PNG
        theme: "scientific", "presentation", or "web"
        palette: Color palette

    Values are automatically converted to percentages.

    Returns path to rendered PNG.
    """
    try:
        data = json.loads(data_json)
        segments = data.get("segments", [])
        if not segments:
            return "Error: segments list required"
    except json.JSONDecodeError as e:
        return f"Error: invalid JSON — {e}"

    _apply_theme(theme)
    t = THEMES.get(theme, THEMES["scientific"])
    fig, ax = plt.subplots(figsize=(8, 7))

    labels = [s.get("label","?") for s in segments]
    values = [s.get("value",0) for s in segments]
    colors = _get_colors(palette, len(segments))

    total = sum(values) or 1
    wedges, _texts, autotexts = ax.pie(
        values, labels=None, colors=colors, autopct=lambda pct: f"{pct:.1f}%" if pct > 3 else "",
        startangle=90, pctdistance=0.6,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
    )

    # Legend with percentages
    legend_labels = [f"{lbl} ({val/total*100:.1f}%)" for lbl, val in zip(labels, values, strict=True)]
    ax.legend(wedges, legend_labels, title="", loc="center left",
              bbox_to_anchor=(1, 0.5), frameon=False, fontsize=t["tick_size"])

    for at in autotexts:
        at.set_fontsize(t["tick_size"])
        at.set_fontweight("bold")

    ax.set_title(title, fontweight="bold", pad=15) if title else None
    return _finalize(fig, ax, output, theme)


@mcp.tool()
def radar_chart(
    data_json: str,
    title: str = "",
    output: str = "chart.png",
    theme: str = "scientific",
    palette: str = "muted",
) -> str:
    """Create a radar/spider chart comparing multiple dimensions.

    Perfect for: technology comparison, gap analysis, multi-criteria assessment.

    Args:
        data_json: JSON like {"categories":["Accuracy","Speed","Cost","Scale","UX"],
                              "series":[
                                  {"label":"Method A","values":[8,5,7,6,9]},
                                  {"label":"Method B","values":[6,8,4,7,6]}
                              ]}
        title: Chart title
        output: File path for PNG
        theme: "scientific", "presentation", or "web"
        palette: Color palette

    Values should be on a consistent scale (e.g., 0-10).

    Returns path to rendered PNG.
    """
    try:
        data = json.loads(data_json)
        categories = data.get("categories", [])
        series_list = data.get("series", [])
        if not categories or not series_list:
            return "Error: categories and series are required"
    except json.JSONDecodeError as e:
        return f"Error: invalid JSON — {e}"

    _apply_theme(theme)
    t = THEMES.get(theme, THEMES["scientific"])
    colors = _get_colors(palette, len(series_list))
    N = len(categories)
    angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"projection": "polar"})

    for i, s in enumerate(series_list):
        values = s.get("values", [])
        label = s.get("label", f"Series {i}")
        if len(values) != N:
            return f"Error: series '{label}' length ({len(values)}) != categories ({N})"
        vals = values + values[:1]
        ax.fill(angles, vals, color=colors[i], alpha=0.15)
        ax.plot(angles, vals, "o-", color=colors[i], linewidth=2, markersize=6, label=label)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=t["tick_size"])
    ax.set_title(title, fontweight="bold", pad=40, fontsize=t["title_size"]) if title else None
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.15), frameon=False,
              fontsize=t["tick_size"] - 1, ncol=len(series_list))
    ax.set_yticklabels([])
    ax.grid(True, alpha=0.3)

    return _finalize(fig, ax, output, theme)


if __name__ == "__main__":
    print("PaperForge Chart MCP Server starting...", file=sys.stderr)
    mcp.run()
