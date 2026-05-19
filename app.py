#!/usr/bin/env python3
"""Research Assistant — Flask web UI for thesis research.

Launch:
    flask --app app run
    flask --app app run --port 5050 --debug

Requires researcher.py, common.py, and zot.py in the same directory.
"""
from __future__ import annotations

import html as _html
import logging
import os
import sys
import threading
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, url_for

sys.path.insert(0, str(Path(__file__).parent))

from common import MODELS, ask_model
from researcher import (
    DEFAULT_K,
    DEFAULT_THRESHOLD,
    CHROMA_DIR,
    SESSION_DIR,
    _get_collection,
    _get_index_stats,
    ask_research_question,
    compare_research_question,
    list_sessions as list_research_sessions,
)
from researcher import save_session as save_research_session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(32).hex())


@app.template_filter("safe_nl2br")
def _safe_nl2br(text: str) -> str:
    """Escape HTML, then convert newlines to <br> tags."""
    from markupsafe import escape, Markup
    escaped = escape(text)
    return Markup(escaped.replace("\n", "<br>"))

logger = logging.getLogger("research-assistant")

# Thread-safe background indexing state
_index_lock = threading.Lock()
_index_state = {
    "running": False,
    "progress": 0,
    "total": 0,
    "status": "idle",
    "error": None,
    "stats": None,
}


def _get_index_state():
    """Thread-safe copy of index state."""
    with _index_lock:
        return dict(_index_state)


def _get_index_data():
    """Get current index stats for the UI."""
    if not CHROMA_DIR.exists():
        return {"exists": False, "documents": 0, "chunks": 0}
    try:
        collection = _get_collection()
        stats = _get_index_stats(collection)
        meta = stats.get("index_meta") or {}
        return {
            "exists": True,
            "documents": stats["documents"],
            "chunks": stats["chunks"],
            "embedding_model": meta.get("embedding_model", "unknown"),
            "chunk_size": meta.get("chunk_size", "?"),
            "last_indexed": meta.get("indexed_at", "never"),
        }
    except Exception:
        return {"exists": True, "documents": 0, "chunks": 0, "error": True}


def _run_index_in_background(collection_name: str | None, limit: int | None, force: bool):
    """Run indexing in a background thread, updating _index_state with lock."""
    global _index_state
    with _index_lock:
        _index_state = {"running": True, "progress": 0, "total": 0, "status": "starting", "error": None, "stats": None}

    try:
        from researcher import index_zotero_papers
        stats = index_zotero_papers(
            collection_name=collection_name,
            limit=limit,
            force=force,
        )
        with _index_lock:
            _index_state["stats"] = stats
            _index_state["status"] = "complete"
    except Exception as e:
        with _index_lock:
            _index_state["error"] = str(e)
            _index_state["status"] = "error"
    finally:
        with _index_lock:
            _index_state["running"] = False


def _safe_session_path(name: str) -> Path | None:
    """Resolve session path safely, preventing directory traversal."""
    sanitized = name.lstrip("/").replace("\\", "/").rstrip("/")
    if not sanitized or sanitized.startswith("."):
        return None
    path = (SESSION_DIR / sanitized).resolve()
    if not str(path).startswith(str(SESSION_DIR.resolve())):
        return None
    return path


def _render_markdown_to_html(text: str) -> str:
    """Convert session markdown to safe HTML using html.escape on all content."""
    import re
    lines = text.split("\n")
    parts = []
    in_list = False
    in_blockquote = False

    for line in lines:
        if line.startswith("### "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            if in_blockquote:
                parts.append("</blockquote>")
                in_blockquote = False
            parts.append(f"<h3>{_html.escape(line[4:])}</h3>")
        elif line.startswith("## "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            if in_blockquote:
                parts.append("</blockquote>")
                in_blockquote = False
            parts.append(f"<h2>{_html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<h1>{_html.escape(line[2:])}</h1>")
        elif line.startswith("- "):
            if not in_list:
                parts.append('<ul class="source-list">')
                in_list = True
            content = _html.escape(line[2:])
            content = re.sub(r'@([a-zA-Z][a-zA-Z0-9_:.-]*)', r'<code class="citekey">@\1</code>', content)
            parts.append(f"<li>{content}</li>")
        elif line.startswith("> "):
            if not in_blockquote:
                parts.append('<blockquote class="excerpt">')
                in_blockquote = True
            parts.append(f"<p>{_html.escape(line[2:])}</p>")
        elif line.startswith("---"):
            if in_list:
                parts.append("</ul>")
                in_list = False
            if in_blockquote:
                parts.append("</blockquote>")
                in_blockquote = False
            parts.append("<hr>")
        elif line.startswith("**") and line.endswith("**"):
            parts.append(f"<p><strong>{_html.escape(line[2:-2])}</strong></p>")
        elif line.strip():
            if in_list:
                parts.append("</ul>")
                in_list = False
            if in_blockquote:
                parts.append("</blockquote>")
                in_blockquote = False
            content = _html.escape(line)
            content = re.sub(r'\[@([a-zA-Z][a-zA-Z0-9_:.-]*)\]', r'<code class="citekey">[@\1]</code>', content)
            content = re.sub(r'@([a-zA-Z][a-zA-Z0-9_:.-]*)', r'<code class="citekey">@\1</code>', content)
            parts.append(f"<p>{content}</p>")

    if in_list:
        parts.append("</ul>")
    if in_blockquote:
        parts.append("</blockquote>")

    return "\n".join(parts)


def _safe_int(value: str | None, default: int) -> int:
    """Parse an int safely, returning default on failure."""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def _safe_float(value: str | None, default: float) -> float:
    """Parse a float safely, returning default on failure."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


# ── Routes ──────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    """Dashboard homepage."""
    index_data = _get_index_data()
    sessions = list_research_sessions()[:5]
    state = _get_index_state()
    return render_template("index.html", index=index_data, sessions=sessions, models=MODELS, index_state=state)


@app.route("/ask", methods=["GET", "POST"])
def ask():
    """Ask a research question with RAG."""
    result = None
    question = ""
    model = "claude"
    k = DEFAULT_K
    threshold = DEFAULT_THRESHOLD
    save_name = ""

    if request.method == "POST":
        question = request.form.get("question", "").strip()
        model = request.form.get("model", "claude")
        k = _safe_int(request.form.get("k"), DEFAULT_K)
        threshold = _safe_float(request.form.get("threshold"), DEFAULT_THRESHOLD)
        save_name = request.form.get("save_name", "").strip()

        if question and _get_index_data()["exists"]:
            try:
                result = ask_research_question(
                    question=question,
                    model=model,
                    temperature=0.3,
                    k=k,
                    threshold=threshold,
                )
                if save_name:
                    save_research_session(save_name, question, result)
            except Exception as e:
                result = {"answer": f"Error: {e}", "sources": [], "model": model, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}

    return render_template(
        "ask.html",
        question=question,
        model=model,
        k=k,
        threshold=threshold,
        save_name=save_name,
        result=result,
        models=MODELS,
        index_exists=_get_index_data()["exists"],
    )


@app.route("/compare", methods=["GET", "POST"])
def compare():
    """Compare answers from multiple models."""
    outcomes = None
    question = ""
    selected_models = ["claude", "gemini"]
    use_rag = True
    save_name = ""

    if request.method == "POST":
        question = request.form.get("question", "").strip()
        selected_models = request.form.getlist("models")
        use_rag = request.form.get("use_rag") == "on"
        save_name = request.form.get("save_name", "").strip()

        if question and selected_models:
            try:
                if use_rag and _get_index_data()["exists"]:
                    outcomes = compare_research_question(
                        question=question,
                        models=selected_models,
                    )
                else:
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    outcomes = {}
                    with ThreadPoolExecutor(max_workers=len(selected_models)) as executor:
                        futures = {
                            executor.submit(ask_model, question, model=m, temperature=0.3): m
                            for m in selected_models
                        }
                        for future in as_completed(futures):
                            m = futures[future]
                            try:
                                r = future.result()
                                outcomes[m] = {
                                    "answer": r["text"],
                                    "model": MODELS.get(m, m),
                                    "input_tokens": r.get("input_tokens", 0),
                                    "output_tokens": r.get("output_tokens", 0),
                                    "cost": r.get("cost", 0.0),
                                }
                            except Exception as e:
                                outcomes[m] = {"answer": f"Error: {e}", "model": m, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}

                if save_name:
                    try:
                        from researcher import _save_comparison_session
                        _save_comparison_session(save_name, question, outcomes)
                    except Exception as e:
                        logger.warning("Failed to save comparison session: %s", e)
            except Exception as e:
                outcomes = {"error": {"answer": str(e), "model": "", "input_tokens": 0, "output_tokens": 0, "cost": 0.0}}

    return render_template(
        "compare.html",
        question=question,
        selected_models=selected_models,
        use_rag=use_rag,
        save_name=save_name,
        outcomes=outcomes,
        models=MODELS,
        index_exists=_get_index_data()["exists"],
    )


@app.route("/sessions")
def sessions():
    """Browse past research sessions."""
    session_list = list_research_sessions()
    return render_template("sessions.html", sessions=session_list)


@app.route("/sessions/<name>")
def view_session(name):
    """View a saved session (path-traversal protected)."""
    path = _safe_session_path(name)
    if not path or not path.exists():
        return "Session not found", 404
    content = path.read_text(encoding="utf-8")
    safe_html = _render_markdown_to_html(content)
    return render_template("sessions.html", session_content=safe_html, session_name=name, sessions=list_research_sessions())


@app.route("/sessions/<name>/delete", methods=["POST"])
def delete_session(name):
    """Delete a session (path-traversal protected)."""
    path = _safe_session_path(name)
    if not path:
        return "Invalid session name", 400
    if path.exists():
        path.unlink()
    return redirect(url_for("sessions"))


@app.route("/stats")
def stats_api():
    """JSON endpoint for index stats."""
    return jsonify(_get_index_data())


@app.route("/index/start", methods=["POST"])
def index_start():
    """Start background indexing."""
    with _index_lock:
        if _index_state["running"]:
            return jsonify({"error": "Indexing already in progress"}), 409
        _index_state["running"] = True

    collection = request.form.get("collection", "").strip() or None
    limit_raw = request.form.get("limit", "").strip()
    limit = _safe_int(limit_raw, 0) if limit_raw else None
    force = request.form.get("force") == "on"

    thread = threading.Thread(
        target=_run_index_in_background,
        args=(collection, limit, force),
        daemon=True,
    )
    thread.start()
    return jsonify({"status": "started"})


@app.route("/index/status")
def index_status():
    """JSON endpoint for indexing progress."""
    return jsonify(_get_index_state())


@app.route("/index")
def index_page():
    """Index management page."""
    state = _get_index_state()
    return render_template("index.html", index=_get_index_data(), sessions=list_research_sessions()[:5], models=MODELS, index_state=state, tab="index")


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="127.0.0.1", port=5000)
