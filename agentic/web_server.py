"""PaperForge Flask blueprint — web UI for the paper generation pipeline.

Provides:
    - GET  /paperforge            — form page (code path, summary, options)
    - POST /paperforge/run        — start pipeline, returns job ID
    - GET  /paperforge/progress   — SSE stream of agent progress
    - GET  /paperforge/result/<id> — view/download results

Integrate into the main Flask app:
    from agentic.web_server import paperforge_bp
    app.register_blueprint(paperforge_bp)

Or run standalone:
    python -m agentic.web_server
"""
from __future__ import annotations

import json
import os
import sys
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

# ── Job store ──────────────────────────────────────────────────────────────

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

THESIS_ROOT = Path(os.getenv("THESIS_ROOT", str(Path.home() / "thesis")))


def _get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        return _jobs.get(job_id)


def _update_job(job_id: str, **kwargs):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


# ── Pipeline runner ────────────────────────────────────────────────────────

def _run_pipeline_in_thread(job_id: str, code_path: str, summary: str,
                             output_dir: str, max_rewrites: int,
                             mode: str = "code", topic: str = ""):
    """Run the full pipeline in a background thread, emitting progress events.

    `mode` is "code" (codebase -> paper) or "review" (topic -> review article
    via autonomous web research).
    """
    import io
    import re

    _update_job(job_id, status="running", started_at=time.time())

    events: list[dict] = []
    _update_job(job_id, events=events)

    # Capture stderr from the orchestrator's _log calls
    captured_stderr = io.StringIO()
    original_stderr = sys.stderr
    _sys = sys

    try:
        _sys.stderr = captured_stderr

        import agentic.orchestrator as orch
        from agentic.orchestrator import build_graph, build_review_graph, load_caches
        from agentic.state import make_initial_state

        orch.MIN_SECTION_SCORE = 7

        review = mode == "review"
        state = make_initial_state(
            code_path="" if review else str(Path(code_path).expanduser().resolve()),
            user_summary=topic if review else summary,
            output_dir=str(Path(output_dir).expanduser().resolve()),
            max_rewrites=max_rewrites,
        )
        if review:
            state["research_topic"] = topic
            state["review_mode"] = True
        cache_updates = load_caches(state)
        style_loaded = bool(state.get("style_guide"))
        tells_loaded = bool(state.get("ai_tells"))
        state.update(cache_updates)

        events.append({
            "type": "status",
            "message": (
                f"Caches: style={'✓' if style_loaded else '✗'} "
                f"tells={'✓' if tells_loaded else '✗'}. "
                "Building pipeline..."
            ),
        })
        _update_job(job_id, events=events)

        graph = build_review_graph() if review else build_graph()
        _update_job(job_id, events=events)

        # Run the graph
        final_state = graph.invoke(state)

        # Restore stderr and parse captured progress
        _sys.stderr = original_stderr
        progress_lines = captured_stderr.getvalue().splitlines()
        prog_re = re.compile(r"^\s*\[([^\]]+)\]\s*(.*)$")
        for line in progress_lines:
            m = prog_re.match(line.strip())
            if m:
                events.append({
                    "type": "agent",
                    "agent": m.group(1),
                    "message": m.group(2),
                })
        _update_job(job_id, events=events)

        out_dir = Path(state["output_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)

        results = {}

        if final_state.get("draft"):
            draft_path = out_dir / "paper.md"
            draft_path.write_text(final_state["draft"], encoding="utf-8")
            results["draft_path"] = str(draft_path)
            results["draft_preview"] = final_state["draft"][:3000]

        if final_state.get("assessment"):
            assess_path = out_dir / "assessment.json"
            assess_path.write_text(
                json.dumps(final_state["assessment"], indent=2), encoding="utf-8")
            results["assessment"] = final_state["assessment"]

        if final_state.get("originality_score"):
            score_path = out_dir / "originality.json"
            score_path.write_text(
                json.dumps(final_state["originality_score"], indent=2),
                encoding="utf-8")
            results["originality"] = final_state["originality_score"]

        agent_calls = final_state.get("agent_calls", [])
        total_cost = sum(c.get("cost", 0) or 0 for c in agent_calls)

        results.update({
            "agent_calls": len(agent_calls),
            "text_rewrites": final_state.get("text_rewrite_count", 0),
            "figure_rewrites": final_state.get("figure_rewrite_count", 0),
            "estimated_cost": round(total_cost, 4),
            "output_dir": str(out_dir),
        })

        events.append({"type": "complete", "results": results})
        _update_job(job_id, status="complete", events=events, results=results,
                     completed_at=time.time())

    except Exception as e:
        _sys.stderr = original_stderr
        events.append({"type": "error", "message": str(e)})
        _update_job(job_id, status="error", events=events, error=str(e))


# ── Routes ─────────────────────────────────────────────────────────────────


@paperforge_bp.route("/paperforge")
def paperforge_page():
    """Render the PaperForge form page."""
    return render_template("paperforge.html")


@paperforge_bp.route("/paperforge/run", methods=["POST"])
def paperforge_run():
    """Start a pipeline run. Returns JSON with job_id.

    Two modes: "code" (codebase -> paper) needs `code_path` + `summary`;
    "review" (topic -> review article) needs `topic`.
    """
    mode = request.form.get("mode", "code").strip() or "code"
    code_path = request.form.get("code_path", "").strip()
    summary = request.form.get("summary", "").strip()
    topic = request.form.get("topic", "").strip()
    output_dir = request.form.get("output_dir", "").strip()
    max_rewrites = int(request.form.get("max_rewrites", "3"))

    if mode == "review":
        if not topic:
            return jsonify({"error": "A research topic is required for review mode."}), 400
    else:
        if not code_path or not summary:
            return jsonify({"error": "Code path and summary are required."}), 400
        if not Path(code_path).expanduser().exists():
            return jsonify({"error": f"Code path does not exist: {code_path}"}), 400

    if not output_dir:
        label = "review" if mode == "review" else "paperforge"
        output_dir = str(THESIS_ROOT / "output" / f"{label}-{uuid.uuid4().hex[:8]}")

    job_id = uuid.uuid4().hex[:12]

    with _jobs_lock:
        _jobs[job_id] = {
            "id": job_id,
            "status": "starting",
            "mode": mode,
            "code_path": code_path,
            "summary": summary,
            "topic": topic,
            "output_dir": output_dir,
            "max_rewrites": max_rewrites,
            "events": [],
            "created_at": time.time(),
        }

    thread = threading.Thread(
        target=_run_pipeline_in_thread,
        args=(job_id, code_path, summary, output_dir, max_rewrites),
        kwargs={"mode": mode, "topic": topic},
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id, "status": "started"})


@paperforge_bp.route("/paperforge/progress/<job_id>")
def paperforge_progress(job_id: str):
    """SSE endpoint — streams progress events for a running job."""
    def generate():
        last_idx = 0
        while True:
            job = _get_job(job_id)
            if job is None:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
                return

            events = job.get("events", [])
            while last_idx < len(events):
                yield f"data: {json.dumps(events[last_idx])}\n\n"
                last_idx += 1

            if job["status"] in ("complete", "error"):
                yield f"data: {json.dumps({'type': 'done', 'status': job['status']})}\n\n"
                return

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


@paperforge_bp.route("/paperforge/result/<job_id>")
def paperforge_result(job_id: str):
    """Return job results as JSON."""
    job = _get_job(job_id)
    if job is None:
        return jsonify({"error": "Job not found"}), 404

    return jsonify({
        "status": job["status"],
        "results": job.get("results"),
        "error": job.get("error"),
    })


@paperforge_bp.route("/paperforge/download/<job_id>/paper.md")
def paperforge_download_paper(job_id: str):
    """Download the generated paper."""
    job = _get_job(job_id)
    if not job or not job.get("results"):
        return "Not found", 404

    draft_path = job["results"].get("draft_path")
    if not draft_path or not Path(draft_path).exists():
        return "Paper not found", 404

    return send_file(draft_path, mimetype="text/markdown",
                     as_attachment=True, download_name="paper.md")


@paperforge_bp.route("/paperforge/jobs")
def paperforge_jobs():
    """List all jobs (for the sidebar status)."""
    with _jobs_lock:
        job_list = [
            {
                "id": j["id"],
                "status": j["status"],
                "code_path": j.get("code_path", ""),
                "created_at": j.get("created_at", 0),
            }
            for j in _jobs.values()
        ]
    return jsonify(sorted(job_list, key=lambda x: x["created_at"], reverse=True))


# ── Standalone runner ──────────────────────────────────────────────────────

def _cli():
    """Run PaperForge web UI standalone."""
    from flask import Flask
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(32).hex())
    app.register_blueprint(paperforge_bp)

    host = os.environ.get("PF_HOST", "127.0.0.1")
    port = int(os.environ.get("PF_PORT", "5055"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    print(f"PaperForge UI → http://{host}:{port}/paperforge")
    app.run(debug=debug, host=host, port=port)


if __name__ == "__main__":
    _cli()
