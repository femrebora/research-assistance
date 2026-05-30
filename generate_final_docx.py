#!/usr/bin/env python3
"""Generate final DOCX from a pipeline run with real charts embedded."""
import json, re, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agentic.docx_export import export_to_docx


def main(job_id: str, charts_source: str | None = None):
    """Load pipeline state, embed charts, generate DOCX.

    Args:
        job_id: Pipeline job ID (e.g. '25ff9f7f2c3f')
        charts_source: Directory with pre-rendered charts (optional)
    """
    state_path = Path.home() / "thesis" / "runs" / job_id / "state.json"
    if not state_path.exists():
        print(f"State not found: {state_path}")
        sys.exit(1)

    state = json.loads(state_path.read_text())
    draft = state.get("draft", "")
    out_dir = Path(state["output_dir"])
    figs_dir = out_dir / "figures"
    figs_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / "paper_final.docx"
    alt_dest = Path("/home/bogrum/thesis/output/chem713-paper/CHEM713_final.docx")

    # Copy real charts if provided
    if charts_source:
        src = Path(charts_source)
        chart_files = [
            "fig1_rmsd.png",
            "fig2_atp_energy.png",
            "fig3_allosteric_effect.png",
            "fig4_system_radar.png",
        ]
        for f in chart_files:
            if (src / f).exists():
                shutil.copy(src / f, figs_dir / f)
                print(f"  Copied {f}")

    # Clean placeholders
    draft = re.sub(r'\[FIG\s+\w+\s*\|[^\]]+\]', '', draft)
    draft = re.sub(r'\[FIGURE:\s*[^\]]+\]', '', draft)

    # Auto-detect available charts in figures_dir
    available = sorted(figs_dir.glob("*.png"))
    fig_block = ""
    for i, png in enumerate(available):
        name = png.stem.replace("_", " ").title()
        fig_block += f"![Figure {i+1}: {name}]({png.name})\n"
        fig_block += f"*Figure {i+1}: {name}.*\n\n"

    # Insert before Results or at midpoint
    rp = draft.find("## Results")
    if rp < 0:
        rp = draft.find("## Discussion")
    if rp < 0:
        rp = len(draft) // 2
    draft = draft[:rp] + "\n" + fig_block + "\n" + draft[rp:]

    # Save patched paper
    (out_dir / "paper.md").write_text(draft)
    print(f"Paper: {len(draft)} chars, {len(available)} figures")

    # Generate DOCX
    for d in [dest, alt_dest]:
        try:
            export_to_docx(draft, str(figs_dir), str(d))
            print(f"DOCX: {d} ({Path(d).stat().st_size / 1024:.0f} KB)")
        except Exception as e:
            print(f"  Failed {d}: {e}")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Generate final DOCX from pipeline run")
    p.add_argument("job_id", help="Pipeline job ID")
    p.add_argument("--charts", "-c", help="Directory with pre-rendered charts")
    args = p.parse_args()
    main(args.job_id, args.charts)
