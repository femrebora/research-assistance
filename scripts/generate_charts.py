#!/usr/bin/env python3
"""Publication-quality chart generation for academic review articles.

Generates matplotlib/seaborn figures with professional styling suitable for
journal publication. Replaces the Mermaid-based approach that produced
poorly-styled charts.

Chart types:
  - grouped_bar:    Market comparisons, technology comparisons
  - timeline:       Regulatory milestones, breakthrough chronology
  - bubble_chart:   Company landscape (funding vs maturity)
  - heatmap:        Technology/method comparison matrix
  - trend_line:     Market growth over time

Usage:
  from generate_charts import grouped_bar, timeline, bubble_chart

  grouped_bar(
      categories=["Genomics", "Proteomics", "Companion Dx"],
      values=[22.5, 8.3, 15.7],
      title="Market Size by Segment (2026, $B)",
      output="chart.png",
  )
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # non-interactive backend

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker  # noqa: F401  # kept for user extensions
import numpy as np

# ── Publication-quality defaults ─────────────────────────────────────────────

# Professional muted scientific color palette
COLORS = {
    "blue": "#2166ac",
    "red": "#b2182b",
    "green": "#4daf4a",
    "orange": "#ff7f00",
    "purple": "#984ea3",
    "teal": "#00a896",
}
COLOR_LIST = ["#2166ac", "#b2182b", "#4daf4a", "#ff7f00", "#984ea3", "#00a896"]

# matplotlib RC params for publication quality (white background, clean)
RC_PARAMS = {
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "black",
    "axes.linewidth": 0.8,
    "axes.grid": False,
    "grid.alpha": 0.3,
    "grid.color": "#cccccc",
    "grid.linestyle": "--",
    "grid.linewidth": 0.4,
    "xtick.color": "black",
    "ytick.color": "black",
    "xtick.direction": "out",
    "ytick.direction": "out",
    "xtick.major.size": 3,
    "ytick.major.size": 3,
    "xtick.minor.size": 1.5,
    "ytick.minor.size": 1.5,
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "axes.titlepad": 8,
    "axes.labelpad": 6,
}

matplotlib.rcParams.update(RC_PARAMS)

import seaborn as sns  # noqa: E402  (must follow rcParams)

sns.set_style("white", RC_PARAMS)
sns.set_context("paper", font_scale=1.0)


# ── Internal helpers ─────────────────────────────────────────────────────────


def _save_figure(fig: plt.Figure, output: str, dpi: int = 300) -> str:
    """Save a figure to disk with consistent publication settings."""
    output_path = Path(output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        str(output_path),
        dpi=dpi,
        bbox_inches="tight",
        pad_inches=0.05,
        facecolor="white",
        edgecolor="none",
    )
    plt.close(fig)
    return str(output_path)


def _apply_title_and_labels(
    ax: plt.Axes,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    title_size: int = 14,
    label_size: int = 12,
    tick_size: int = 10,
) -> None:
    """Apply consistent typography to axes (title 14pt, labels 12pt, ticks 10pt)."""
    if title:
        ax.set_title(title, fontsize=title_size, fontweight="bold", pad=10)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=label_size)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=label_size)
    ax.tick_params(axis="both", which="major", labelsize=tick_size)
    ax.tick_params(axis="both", which="minor", labelsize=tick_size - 1)


def _remove_spines(ax: plt.Axes, keep: list[str] | None = None) -> None:
    """Remove excess spines to eliminate chartjunk."""
    if keep is None:
        keep = ["left", "bottom"]
    for spine in list(ax.spines.keys()):
        if spine not in keep:
            ax.spines[spine].set_visible(False)


# ── Chart functions ──────────────────────────────────────────────────────────


def grouped_bar(
    categories: list[str],
    values: list[float] | list[list[float]],
    labels: list[str] | None = None,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    colors: list[str] | None = None,
    width: float = 0.65,
    figsize: tuple[float, float] = (8, 5),
    output: str = "grouped_bar.png",
    dpi: int = 300,
) -> str:
    """Grouped or single-series bar chart for market/technology comparisons.

    Parameters
    ----------
    categories : list of str
        X-axis category labels.
    values : list of float or list of list of float
        Single list of values (one bar per category) or list of lists
        for grouped bars (each sub-list is a group).
    labels : list of str or None
        Series labels for grouped bars (legend). Required when *values*
        is a list of lists.
    title : str
        Chart title.
    xlabel : str
        X-axis label.
    ylabel : str
        Y-axis label.
    colors : list of str or None
        Bar color(s). Defaults to the muted scientific palette.
    width : float
        Total width consumed by bars per category (0-1).
    figsize : (float, float)
        Figure dimensions in inches.
    output : str
        Output PNG path.
    dpi : int
        Output resolution.

    Returns
    -------
    str
        Absolute path to the saved PNG.
    """
    if colors is None:
        colors = COLOR_LIST

    fig, ax = plt.subplots(figsize=figsize)
    _remove_spines(ax)

    x = np.arange(len(categories))

    # Single series -------------------------------------------------------
    if not values:
        raise ValueError("`values` must not be empty.")

    if isinstance(values[0], (list, tuple)):
        # Grouped bar chart
        n_groups = len(values)
        group_width = width / n_groups

        for i, series in enumerate(values):
            offset = (i - n_groups / 2 + 0.5) * group_width
            ax.bar(
                x + offset,
                series,
                group_width,
                label=labels[i] if labels else f"Series {i + 1}",
                color=colors[i % len(colors)],
                edgecolor="white",
                linewidth=0.3,
            )

        if labels:
            ax.legend(fontsize=9, frameon=False)
    else:
        # Single series
        ax.bar(
            x,
            values,
            width,
            color=colors[0],
            edgecolor="white",
            linewidth=0.3,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(categories)

    _apply_title_and_labels(ax, title, xlabel, ylabel)
    return _save_figure(fig, output, dpi)


def timeline(
    events: list[str],
    dates: list[Any],
    values: list[float] | None = None,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    color: str = "#2166ac",
    marker_size: int = 80,
    figsize: tuple[float, float] = (10, 4),
    output: str = "timeline.png",
    dpi: int = 300,
) -> str:
    """Horizontal timeline chart for regulatory milestones or breakthroughs.

    Parameters
    ----------
    events : list of str
        Event labels displayed on the timeline.
    dates : list of numeric or datetime
        Date positions (numeric years or datetime objects).
    values : list of float or None
        Optional magnitude values for variable-sized markers.
    title : str
        Chart title.
    xlabel : str
        X-axis label.
    ylabel : str
        Y-axis label.
    color : str
        Marker and line color.
    marker_size : int
        Base marker size (used when *values* is None).
    figsize : (float, float)
        Figure dimensions in inches.
    output : str
        Output PNG path.
    dpi : int
        Output resolution.

    Returns
    -------
    str
        Absolute path to the saved PNG.
    """
    fig, ax = plt.subplots(figsize=figsize)
    _remove_spines(ax, keep=["bottom"])
    ax.spines["bottom"].set_position(("data", 0))

    y_zero = np.zeros(len(events))

    # Sizing: values-driven or uniform
    marker_sizes = [max(20, abs(v) * 10) for v in values] if values else [marker_size] * len(events)

    ax.scatter(
        dates,
        y_zero,
        s=marker_sizes,
        c=color,
        alpha=0.7,
        edgecolors="white",
        linewidth=0.5,
        zorder=3,
    )

    # Stem lines from baseline up
    for d in dates:
        ax.plot(
            [d, d],
            [0, 0.15],
            color=color,
            linewidth=0.8,
            alpha=0.4,
        )

    # Staggered labels above the timeline
    for i, ev in enumerate(events):
        y_lbl = 0.25 if i % 2 == 0 else 0.45
        ax.annotate(
            ev,
            (dates[i], y_lbl),
            fontsize=8,
            ha="center",
            va="bottom",
            rotation=30,
            color="black",
        )
        ax.plot(
            [dates[i], dates[i]],
            [0.15, y_lbl - 0.02],
            color="#888888",
            linewidth=0.4,
            linestyle=":",
            alpha=0.5,
        )

    ax.set_ylim(-0.3, 0.65)
    ax.set_yticks([])

    _apply_title_and_labels(ax, title, xlabel, ylabel)
    return _save_figure(fig, output, dpi)


def bubble_chart(
    companies: list[str],
    funding: list[float],
    maturity: list[float],
    sizes: list[float] | None = None,
    labels: list[str] | None = None,
    title: str = "Company Landscape",
    xlabel: str = "Funding ($M)",
    ylabel: str = "Technology Maturity",
    color_column: list[float] | None = None,
    colors: list[str] | None = None,
    figsize: tuple[float, float] = (8, 6),
    output: str = "bubble_chart.png",
    dpi: int = 300,
) -> str:
    """Bubble chart for company landscape (funding vs maturity).

    Parameters
    ----------
    companies : list of str
        Company names (rendered inside each bubble).
    funding : list of float
        X-axis values (funding in $M).
    maturity : list of float
        Y-axis values (maturity score, e.g., 0--100).
    sizes : list of float or None
        Bubble areas. Defaults to *funding* scaled by 2 (min 30).
    labels : list of str or None
        Category labels for discrete-color legend.
    title : str
        Chart title.
    xlabel : str
        X-axis label.
    ylabel : str
        Y-axis label.
    color_column : list of float or None
        Numeric column for continuous colour mapping (e.g., employee count).
    colors : list of str or None
        Discrete category colours. Ignored unless *labels* is also provided.
    figsize : (float, float)
        Figure dimensions in inches.
    output : str
        Output PNG path.
    dpi : int
        Output resolution.

    Returns
    -------
    str
        Absolute path to the saved PNG.
    """
    if sizes is None:
        sizes = [max(30, abs(f) * 2) for f in funding]
    if colors is None:
        colors = COLOR_LIST

    fig, ax = plt.subplots(figsize=figsize)
    _remove_spines(ax)

    if color_column is not None:
        # Continuous colour mapping
        sc = ax.scatter(
            funding,
            maturity,
            s=sizes,
            c=color_column,
            cmap="viridis",
            alpha=0.75,
            edgecolors="white",
            linewidth=0.5,
            zorder=3,
        )
        cbar = fig.colorbar(sc, ax=ax, shrink=0.7, pad=0.02)
        cbar.set_label("Color Scale", fontsize=10)
        cbar.ax.tick_params(labelsize=9)
    elif labels is not None:
        # Discrete categories
        seen: dict[str, str] = {}
        for _i, (comp, f, m, s, lbl) in enumerate(  # noqa: B007
            zip(companies, funding, maturity, sizes, labels, strict=False)
        ):
            if lbl not in seen:
                seen[lbl] = colors[len(seen) % len(colors)]
            ax.scatter(
                f,
                m,
                s=s,
                c=seen[lbl],
                label=lbl if lbl not in ax.get_legend_handles_labels()[1] else "",
                alpha=0.75,
                edgecolors="white",
                linewidth=0.5,
                zorder=3,
            )
        ax.legend(fontsize=9, frameon=False, loc="best")
    else:
        ax.scatter(
            funding,
            maturity,
            s=sizes,
            c=colors[0],
            alpha=0.7,
            edgecolors="white",
            linewidth=0.5,
            zorder=3,
        )

    # Label each bubble with company name
    for comp, f, m in zip(companies, funding, maturity, strict=False):
        ax.annotate(
            comp,
            (f, m),
            fontsize=7,
            ha="center",
            va="center",
            color="white",
            fontweight="bold",
            alpha=0.9,
        )

    _apply_title_and_labels(ax, title, xlabel, ylabel)
    return _save_figure(fig, output, dpi)


def heatmap(
    data: list[list[float]],
    row_labels: list[str],
    col_labels: list[str],
    title: str = "Technology Comparison Matrix",
    xlabel: str = "",
    ylabel: str = "",
    cmap: str = "Blues",
    annotate: bool = True,
    fmt: str = ".2f",
    figsize: tuple[float, float] = (8, 6),
    output: str = "heatmap.png",
    dpi: int = 300,
) -> str:
    """Heatmap for technology/method comparison matrix.

    Parameters
    ----------
    data : list of list of float
        2-D array of values (rows x columns).
    row_labels : list of str
        Labels for rows (e.g., technologies).
    col_labels : list of str
        Labels for columns (e.g., evaluation criteria).
    title : str
        Chart title.
    xlabel : str
        X-axis label.
    ylabel : str
        Y-axis label.
    cmap : str
        Matplotlib colormap name.
    annotate : bool
        Show value annotations in each cell.
    fmt : str
        Format string for annotations (e.g., ``".2f"``, ``".0f"``, ``"d"``).
    figsize : (float, float)
        Figure dimensions in inches.
    output : str
        Output PNG path.
    dpi : int
        Output resolution.

    Returns
    -------
    str
        Absolute path to the saved PNG.
    """
    fig, ax = plt.subplots(figsize=figsize)

    data_arr = np.array(data)

    sns.heatmap(
        data_arr,
        annot=annotate,
        fmt=fmt,
        xticklabels=col_labels,
        yticklabels=row_labels,
        cmap=cmap,
        ax=ax,
        cbar_kws={"shrink": 0.8, "label": ""},
        linewidths=0.5,
        linecolor="white",
        square=False,
    )

    ax.tick_params(axis="both", which="major", labelsize=10)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=35, ha="right")

    _apply_title_and_labels(ax, title, xlabel, ylabel)
    return _save_figure(fig, output, dpi)


def trend_line(
    years: list[Any],
    series: list[float] | dict[str, list[float]],
    title: str = "Market Growth Trend",
    xlabel: str = "Year",
    ylabel: str = "Value",
    colors: list[str] | None = None,
    linestyles: list[str] | None = None,
    markers: list[str] | None = None,
    fill_below: bool = True,
    figsize: tuple[float, float] = (9, 5),
    output: str = "trend_line.png",
    dpi: int = 300,
) -> str:
    """Line chart for market growth over time.

    Parameters
    ----------
    years : list of numeric
        X-axis values (e.g., years).
    series : list of float or dict of str -> list of float
        Single list of Y values, or a dict mapping series labels to value
        lists for multiple lines.
    title : str
        Chart title.
    xlabel : str
        X-axis label.
    ylabel : str
        Y-axis label.
    colors : list of str or None
        Line colours. Defaults to the muted scientific palette.
    linestyles : list of str or None
        Line styles cycled for multi-series plots.
        Default: ``["-", "--", ":", "-."]``.
    markers : list of str or None
        Marker styles cycled for multi-series plots.
        Default: ``["o", "s", "^", "D"]``.
    fill_below : bool
        Fill area below the line (single-series only).
    figsize : (float, float)
        Figure dimensions in inches.
    output : str
        Output PNG path.
    dpi : int
        Output resolution.

    Returns
    -------
    str
        Absolute path to the saved PNG.
    """
    if colors is None:
        colors = COLOR_LIST
    if linestyles is None:
        linestyles = ["-", "--", ":", "-."]
    if markers is None:
        markers = ["o", "s", "^", "D"]

    fig, ax = plt.subplots(figsize=figsize)
    _remove_spines(ax)

    years_arr = np.array(years)

    if isinstance(series, dict):
        for i, (label, vals) in enumerate(series.items()):
            ax.plot(
                years_arr,
                vals,
                label=label,
                color=colors[i % len(colors)],
                linestyle=linestyles[i % len(linestyles)],
                marker=markers[i % len(markers)],
                linewidth=1.5,
                markersize=5,
                alpha=0.85,
            )
        ax.legend(fontsize=9, frameon=False, loc="best")
    else:
        ax.plot(
            years_arr,
            series,
            color=colors[0],
            linestyle="-",
            marker="o",
            linewidth=1.5,
            markersize=5,
            alpha=0.85,
        )
        if fill_below:
            ax.fill_between(years_arr, series, alpha=0.08, color=colors[0])

    _apply_title_and_labels(ax, title, xlabel, ylabel)
    return _save_figure(fig, output, dpi)


# ── Demo / smoke test ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    demo_dir = Path(__file__).resolve().parent.parent / "assets" / "demo_charts"
    demo_dir.mkdir(exist_ok=True)

    print("Generating demo charts...", file=sys.stderr)

    # 1. Grouped bar (single series)
    p = grouped_bar(
        categories=["Genomics", "Proteomics", "Companion Dx", "Liquid Biopsy", "Single Cell"],
        values=[22.5, 8.3, 15.7, 6.2, 4.8],
        title="Market Size by Segment (2026, $B)",
        xlabel="Segment",
        ylabel="Market Size ($B)",
        output=str(demo_dir / "demo_grouped_bar.png"),
    )
    print(f"  {p}", file=sys.stderr)

    # 1b. Grouped bar (multi-series)
    p = grouped_bar(
        categories=["mRNA", "AAV", "LNP", "CRISPR"],
        values=[[8.5, 3.2, 2.1, 1.5], [12.3, 5.1, 3.8, 4.2], [18.7, 7.8, 6.0, 9.5]],
        labels=["2024", "2025", "2026"],
        title="Therapeutic Modality Market ($B)",
        xlabel="Modality",
        ylabel="Market Size ($B)",
        output=str(demo_dir / "demo_grouped_bar_multi.png"),
    )
    print(f"  {p}", file=sys.stderr)

    # 2. Timeline
    p = timeline(
        events=[
            "FDA approves Keytruda",
            "CRISPR first human trial",
            "First mRNA vaccine (COVID-19)",
            "FDA accelerated approval for gene therapy",
            "AI-designed drug enters Phase I",
        ],
        dates=[2014, 2016, 2020, 2022, 2024],
        title="Landmark Events in Precision Medicine",
        xlabel="Year",
        output=str(demo_dir / "demo_timeline.png"),
    )
    print(f"  {p}", file=sys.stderr)

    # 3. Bubble chart
    p = bubble_chart(
        companies=["23andMe", "Tempus", "Grail", "Illumina", "Guardant"],
        funding=[850, 1300, 2000, 6500, 750],
        maturity=[45, 72, 68, 92, 78],
        sizes=[500, 800, 1200, 2000, 600],
        title="Precision Medicine Company Landscape",
        output=str(demo_dir / "demo_bubble.png"),
    )
    print(f"  {p}", file=sys.stderr)

    # 4. Heatmap
    p = heatmap(
        data=[
            [0.95, 0.70, 0.30],
            [0.85, 0.90, 0.50],
            [0.60, 0.75, 0.85],
            [0.40, 0.55, 0.95],
        ],
        row_labels=["WGS", "WES", "Panel-seq", "RNA-seq"],
        col_labels=["Sensitivity", "Specificity", "Cost-Effectiveness"],
        title="Technology Performance Comparison",
        output=str(demo_dir / "demo_heatmap.png"),
    )
    print(f"  {p}", file=sys.stderr)

    # 5. Trend line (multi-series)
    p = trend_line(
        years=[2020, 2021, 2022, 2023, 2024, 2025, 2026],
        series={
            "Precision Medicine": [50, 65, 82, 100, 125, 155, 190],
            "Gene Therapy": [8, 12, 18, 25, 35, 48, 65],
            "Liquid Biopsy": [3, 5, 8, 13, 20, 30, 45],
        },
        title="Market Growth by Segment ($B)",
        xlabel="Year",
        ylabel="Market Size ($B)",
        output=str(demo_dir / "demo_trend.png"),
    )
    print(f"  {p}", file=sys.stderr)

    # 5b. Trend line (single series with fill)
    p = trend_line(
        years=[2020, 2021, 2022, 2023, 2024, 2025, 2026],
        series=[50, 68, 85, 105, 130, 160, 195],
        title="Precision Medicine Market Growth ($B)",
        xlabel="Year",
        ylabel="Market Size ($B)",
        fill_below=True,
        output=str(demo_dir / "demo_trend_single.png"),
    )
    print(f"  {p}", file=sys.stderr)

    print("Done.", file=sys.stderr)
