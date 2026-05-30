"""PaperForge Flask blueprint — interactive web UI for paper generation.

Routes:
  GET  /paperforge                    — main form + workspace page
  GET  /paperforge/workspace/<id>     — interactive workspace with sections + figures
  POST /paperforge/run                — start initial generation (code_analyst → writer)
  GET  /paperforge/progress/<id>      — SSE stream of pipeline events
  GET  /paperforge/state/<id>         — full pipeline state as JSON
  POST /paperforge/<id>/feedback      — submit per-section feedback
  POST /paperforge/<id>/assess        — run assessor → rewriter loop
  POST /paperforge/<id>/figure-feedback — regenerate a specific figure
  POST /paperforge/<id>/finalize      — plagiarism check → finalize
  GET  /paperforge/<id>/figure/<idx>/png — serve generated figure PNG
  GET  /paperforge/download/<id>/paper.md   — download markdown
  GET  /paperforge/download/<id>/paper.docx — download DOCX
  GET  /paperforge/jobs               — list all jobs
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

from flask import Blueprint, Response, jsonify, render_template, request, send_file

paperforge_bp = Blueprint(
    "paperforge",
    __name__,
    template_folder="templates",
    static_folder="static",
)

THESIS_ROOT = Path(os.getenv("THESIS_ROOT", str(Path.home() / "thesis")))


# ── Page routes ────────────────────────────────────────────────────────────

@paperforge_bp.route("/paperforge")
def paperforge_page():
    """Main page — uses Research Assistant base layout when available."""
    try:
        return render_template("paperforge.html", active_route="/paperforge",
                               tool_groups={}, paperforge_available=True)
    except Exception:
        return render_template("paperforge.html", active_route="/paperforge",
                               tool_groups={}, paperforge_available=True)


@paperforge_bp.route("/paperforge/workspace/<job_id>")
def paperforge_workspace(job_id: str):
    """Interactive workspace for a running/completed job."""
    from agentic.state_store import load_state
    try:
        state = load_state(job_id)
    except FileNotFoundError:
        return "Job not found", 404
    return render_template("paperforge.html", job_id=job_id,
                           active_route="/paperforge",
                           state_json=json.dumps(state, indent=2, ensure_ascii=False))


# ── API: start pipeline ────────────────────────────────────────────────────

@paperforge_bp.route("/paperforge/run", methods=["POST"])
def paperforge_run():
    """Start initial generation: code_analyst → writer. Returns job_id JSON."""
    mode = request.form.get("mode", "code").strip() or "code"
    code_path = request.form.get("code_path", "").strip()
    summary = request.form.get("summary", "").strip()
    topic = request.form.get("topic", "").strip()
    max_rewrites = int(request.form.get("max_rewrites", "3"))

    if mode == "review":
        if not topic:
            return jsonify({"error": "A research topic is required."}), 400
    else:
        if not code_path or not summary:
            return jsonify({"error": "Code path and summary are required."}), 400
        if not Path(code_path).expanduser().exists():
            return jsonify({"error": f"Code path does not exist: {code_path}"}), 400

    output_dir = request.form.get("output_dir", "").strip()
    if output_dir:
        # Validate against path traversal
        resolved = Path(output_dir).expanduser().resolve()
        allowed = (THESIS_ROOT / "output").resolve()
        try:
            resolved.relative_to(allowed)
        except ValueError:
            return jsonify({"error": f"Output dir must be under {allowed}"}), 400
        output_dir = str(resolved)
    else:
        label = "review" if mode == "review" else "paperforge"
        output_dir = str(THESIS_ROOT / "output" / f"{label}-{uuid.uuid4().hex[:8]}")

    job_id = uuid.uuid4().hex[:12]

    from agentic.state_store import append_event, init_state
    init_state(job_id, {
        "mode": mode,
        "code_path": code_path,
        "summary": summary,
        "topic": topic,
        "output_dir": output_dir,
        "max_rewrites": max_rewrites,
    })
    append_event(job_id, {"type": "status", "message": "Starting pipeline..."})

    from agentic.pipeline_runner import run_generate
    thread = threading.Thread(target=run_generate, args=(job_id,), daemon=True)
    thread.start()

    return jsonify({"job_id": job_id, "status": "started"})


# ── API: SSE progress ──────────────────────────────────────────────────────

@paperforge_bp.route("/paperforge/progress/<job_id>")
def paperforge_progress(job_id: str):
    """SSE endpoint — streams events from the job's event log."""
    def generate():
        from agentic.state_store import get_events, load_state
        last_idx = 0
        done = False
        while not done:
            events, new_idx = get_events(job_id, last_idx)
            for evt in events[last_idx:]:
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
            last_idx = new_idx

            try:
                state = load_state(job_id)
                if state.get("status") in ("complete", "error", "draft_ready"):
                    if state.get("status") == "draft_ready":
                        yield f"data: {json.dumps({'type': 'done', 'status': 'draft_ready'})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'done', 'status': state['status']})}\n\n"
                    done = True
            except FileNotFoundError:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
                done = True

            if not done:
                time.sleep(0.5)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── API: state ─────────────────────────────────────────────────────────────

@paperforge_bp.route("/paperforge/state/<job_id>")
def paperforge_state(job_id: str):
    """Return full pipeline state as JSON."""
    from agentic.state_store import load_state
    try:
        state = load_state(job_id)
    except FileNotFoundError:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(state)


# ── API: section feedback ──────────────────────────────────────────────────

@paperforge_bp.route("/paperforge/<job_id>/feedback", methods=["POST"])
def paperforge_feedback(job_id: str):
    """Apply user feedback to a section. Returns updated section HTML."""
    section_key = request.form.get("section_key", "").strip()
    feedback = request.form.get("feedback", "").strip()

    if not section_key or not feedback:
        return jsonify({"error": "section_key and feedback required"}), 400

    from agentic.pipeline_runner import apply_section_feedback
    result = apply_section_feedback(job_id, section_key, feedback)

    if result.get("error"):
        return jsonify(result), 404

    # Return the updated section data
    from agentic.section_parser import parse_sections
    sections = parse_sections(result.get("draft", ""))
    updated = None
    for s in sections:
        if s["key"] == section_key:
            updated = s
            break
    return jsonify({"status": "ok", "section": updated})


# ── API: ZeroGPT per-section ───────────────────────────────────────────────

@paperforge_bp.route("/paperforge/<job_id>/zerogpt/<section_key>", methods=["POST"])
def paperforge_zerogpt_section(job_id: str, section_key: str):
    """Run actual ZeroGPT check on a single section. Returns updated score."""
    from agentic.pipeline_runner import zerogpt_check_section
    result = zerogpt_check_section(job_id, section_key)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)


# ── API: revert section ────────────────────────────────────────────────────

@paperforge_bp.route("/paperforge/<job_id>/revert/<section_key>", methods=["POST"])
def paperforge_revert_section(job_id: str, section_key: str):
    """Revert a section to its previous version."""
    from agentic.pipeline_runner import revert_section
    result = revert_section(job_id, section_key)
    if result.get("error"):
        return jsonify(result), 404
    return jsonify(result)


# ── API: assess & revise ───────────────────────────────────────────────────

@paperforge_bp.route("/paperforge/<job_id>/assess", methods=["POST"])
def paperforge_assess(job_id: str):
    """Run assessor → rewriter loop in background. Returns immediately."""
    from agentic.pipeline_runner import run_assess_revise
    thread = threading.Thread(target=run_assess_revise, args=(job_id,), daemon=True)
    thread.start()
    return jsonify({"status": "started"})


# ── API: figure feedback ───────────────────────────────────────────────────

@paperforge_bp.route("/paperforge/<job_id>/figure-feedback", methods=["POST"])
def paperforge_figure_feedback(job_id: str):
    """Regenerate a specific figure with user feedback."""
    try:
        figure_index = int(request.form.get("figure_index", "0"))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid figure_index"}), 400
    feedback = request.form.get("feedback", "").strip()

    if not feedback:
        return jsonify({"error": "feedback required"}), 400

    from agentic.state_store import append_event, load_state, save_state
    state = load_state(job_id)
    figures = state.get("figures") or []

    if figure_index >= len(figures):
        return jsonify({"error": f"Figure index {figure_index} out of range"}), 404

    # Run figure gen with targeted feedback
    from agentic.agents.figure_gen import run_figure_gen
    state["figure_descriptions"] = f"Regenerate Figure {figure_index + 1}: {feedback}"
    delta = run_figure_gen(state)
    state.update(delta)
    save_state(job_id, state)
    append_event(job_id, {"type": "figure_ready", "index": figure_index})

    return jsonify({"status": "ok"})


# ── API: finalize ──────────────────────────────────────────────────────────

@paperforge_bp.route("/paperforge/<job_id>/finalize", methods=["POST"])
def paperforge_finalize(job_id: str):
    """Run plagiarism → figures → complete. Background thread."""
    from agentic.pipeline_runner import run_finalize
    thread = threading.Thread(target=run_finalize, args=(job_id,), daemon=True)
    thread.start()
    return jsonify({"status": "started"})


# ── Figure serving ─────────────────────────────────────────────────────────

@paperforge_bp.route("/paperforge/<job_id>/figure/<int:index>/png")
def paperforge_figure_png(job_id: str, index: int):
    """Serve a generated figure PNG."""
    from agentic.state_store import load_state
    try:
        state = load_state(job_id)
    except FileNotFoundError:
        return "Job not found", 404

    figures = state.get("figures") or []
    if index < 0 or index >= len(figures):
        return "Figure not found", 404
    png_path = figures[index].get("png_path", "")
    if not png_path or not Path(png_path).exists():
        return "Figure PNG not generated yet", 404
    return send_file(png_path, mimetype="image/png")


# ── Downloads ──────────────────────────────────────────────────────────────

@paperforge_bp.route("/paperforge/download/<job_id>/paper.md")
def paperforge_download_md(job_id: str):
    """Download the paper as markdown."""
    from agentic.state_store import load_state
    try:
        state = load_state(job_id)
    except FileNotFoundError:
        return "Not found", 404

    draft = state.get("draft", "")
    if not draft:
        return "No paper generated yet", 404

    from flask import make_response
    resp = make_response(draft)
    resp.headers["Content-Type"] = "text/markdown; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=paper.md"
    return resp


@paperforge_bp.route("/paperforge/download/<job_id>/paper.docx")
def paperforge_download_docx(job_id: str):
    """Generate and download DOCX with embedded figures."""
    from agentic.state_store import load_state
    try:
        state = load_state(job_id)
    except FileNotFoundError:
        return "Not found", 404

    draft = state.get("draft", "")
    if not draft:
        return "No paper generated yet", 404

    out_dir = Path(state.get("output_dir", ""))
    figures_dir = out_dir / "figures"
    docx_path = out_dir / "paper.docx"

    from agentic.docx_export import export_to_docx
    export_to_docx(draft, str(figures_dir), str(docx_path))

    if not docx_path.exists():
        return "DOCX generation failed", 500

    return send_file(str(docx_path), mimetype=(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        as_attachment=True, download_name="paper.docx")


# ── Jobs list ──────────────────────────────────────────────────────────────

@paperforge_bp.route("/paperforge/jobs")
def paperforge_jobs():
    """List all pipeline jobs."""
    from agentic.state_store import list_jobs
    return jsonify(list_jobs())


# ── Standalone runner ──────────────────────────────────────────────────────

def _load_env():
    """Load .env file from project root. Called once on startup."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def _cli():
    """Run PaperForge web UI standalone."""
    _load_env()
    from flask import Flask
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(32).hex())
    # Add Research Assistant template folder so base.html is available
    ra_templates = Path(__file__).resolve().parent.parent / "research_assistant" / "web" / "templates"
    if ra_templates.exists():
        app.jinja_loader.searchpath.insert(0, str(ra_templates))
    app.register_blueprint(paperforge_bp)

    host = os.environ.get("PF_HOST", "127.0.0.1")
    port = int(os.environ.get("PF_PORT", "5055"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    print(f"PaperForge UI → http://{host}:{port}/paperforge")
    app.run(debug=debug, host=host, port=port)


if __name__ == "__main__":
    _cli()
