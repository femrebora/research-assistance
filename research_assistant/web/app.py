#!/usr/bin/env python3
"""Research Assistant — Flask web UI for thesis research.

Launch:
    ra-web                                 # console-script entry (uses RA_PORT, default 5050)
    flask --app research_assistant.web.app run --port 5050 --debug

The app exposes RAG search, model comparison, sessions, index management,
and a generic form page for every CLI tool registered in
`research_assistant.web.tool_runner.TOOL_SPECS`.
"""
from __future__ import annotations

import html as _html
import logging
import os
import threading
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, url_for

from research_assistant.common import MODELS, ask_model
from research_assistant.researcher import (
    CHROMA_DIR,
    DEFAULT_K,
    DEFAULT_THRESHOLD,
    SESSION_DIR,
    _get_collection,
    _get_index_stats,
    ask_research_question,
    compare_research_question,
)
from research_assistant.researcher import (
    list_sessions as list_research_sessions,
)
from research_assistant.researcher import save_session as save_research_session
from research_assistant.web import settings_store
from research_assistant.web.providers import (
    api_provider_status,
    cli_provider_status,
    test_provider,
)
from research_assistant.web.tool_runner import (
    get_spec,
    run_tool,
    specs_by_category,
)
from research_assistant.workspace import defense as defense_mod
from research_assistant.workspace import document as doc_mod
from research_assistant.workspace import editor as editor_mod
from research_assistant.workspace import library as library_mod
from research_assistant.workspace import peer_review as peer_review_mod
from research_assistant.workspace import projects as projects_mod
from research_assistant.workspace import prompts_library as prompts_mod
from research_assistant.workspace import telemetry as telemetry_mod

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(32).hex())


@app.template_filter("safe_nl2br")
def _safe_nl2br(text: str) -> str:
    """Escape HTML, then convert newlines to <br> tags."""
    from markupsafe import Markup, escape
    escaped = escape(text)
    return Markup(escaped.replace("\n", "<br>"))


@app.context_processor
def _inject_nav():
    """Make the tool catalog, active route, and active project available to
    every template."""
    try:
        active_project = projects_mod.get_active_project()
    except Exception:
        active_project = None
    return {
        "tool_groups": specs_by_category(),
        "active_route": request.path if request else "",
        "active_project": active_project,
    }

logger = logging.getLogger("research-assistant")

# PaperForge multi-agent pipeline UI (code->paper and topic->review).
# Registered as a blueprint so /paperforge lives in the same app + nav.
# Guarded: the core UI still loads if PaperForge's module is unavailable.
try:
    from agentic.web_server import paperforge_bp

    app.register_blueprint(paperforge_bp)
    PAPERFORGE_AVAILABLE = True
except Exception as exc:  # keep the core UI usable regardless
    PAPERFORGE_AVAILABLE = False
    logger.warning("PaperForge UI unavailable: %s", exc)


@app.context_processor
def _inject_paperforge_flag():
    """Expose PaperForge availability to every template (for the nav link)."""
    return {"paperforge_available": PAPERFORGE_AVAILABLE}


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
        from research_assistant.researcher import index_zotero_papers
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
            # Single pass — `[...]` form consumed first, remaining bare citekeys after
            content = re.sub(
                r'\[@([a-zA-Z][a-zA-Z0-9_:.-]*)\]|(?<!\w)@([a-zA-Z][a-zA-Z0-9_:.-]*)',
                lambda m: (
                    '<code class="citekey">[@\\1]</code>' if m.group(1)
                    else '<code class="citekey">@\\2</code>'
                ),
                content,
            )
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
    api_providers = api_provider_status()
    cli_providers = cli_provider_status()
    api_ok = sum(1 for p in api_providers if p.configured)
    cli_ok = sum(1 for p in cli_providers if p.found)
    return render_template(
        "index.html",
        index=index_data,
        sessions=sessions,
        models=MODELS,
        index_state=state,
        api_providers=api_providers,
        cli_providers=cli_providers,
        api_ok=api_ok,
        cli_ok=cli_ok,
    )


@app.route("/ask", methods=["GET", "POST"])
def ask():
    """Ask a research question with RAG."""
    result = None
    question = ""
    model = "claude"
    k = DEFAULT_K
    threshold = DEFAULT_THRESHOLD
    save_name = ""

    # Pre-fill question from the prompt-library link, if present.
    prompt_slug = request.args.get("prompt_slug", "").strip()
    if prompt_slug and request.method == "GET":
        prompt = prompts_mod.get_prompt(prompt_slug)
        if prompt:
            question = prompt.body
            model = prompt.recommended_model if prompt.recommended_model in MODELS else model

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
                        from research_assistant.researcher import _save_comparison_session
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


# ── Generic tool routes (driven by tool_runner.TOOL_SPECS) ──────────────────


@app.route("/outline-recommender", methods=["GET"])
def outline_recommender_page():
    """Guided front door for the Outline Recommender tool.

    Renders the standard tool form pre-filled from the active project (topic ←
    research question, discipline, citation style) and posts to the existing
    generic runner at /tools/outline_recommend/run.
    """
    spec = get_spec("outline_recommend")
    if spec is None:
        return redirect(url_for("index"))
    project = active_project_or_none()
    prefill = {}
    if project is not None:
        prefill = {
            "topic": project.research_question or project.title,
            "discipline": project.discipline,
        }
    return render_template("outline_recommender.html", spec=spec, prefill=prefill,
                           project=project)


def active_project_or_none():
    try:
        return projects_mod.get_active_project()
    except Exception:
        return None


@app.route("/tools/<name>", methods=["GET"])
def tool_page(name: str):
    """Render the form for any CLI tool registered in TOOL_SPECS."""
    spec = get_spec(name)
    if spec is None:
        return f"Unknown tool '{name}'", 404
    # The recommender has a dedicated, project-aware front door.
    if name == "outline_recommend":
        return redirect(url_for("outline_recommender_page"))
    return render_template("tools.html", spec=spec)


@app.route("/tools/<name>/run", methods=["POST"])
def tool_run(name: str):
    """HTMX endpoint: execute the tool and return the result partial."""
    spec = get_spec(name)
    if spec is None:
        return f"Unknown tool '{name}'", 404

    result = run_tool(name, request.form)

    from research_assistant.web.tool_runner import (
        _MODULE_BY_NAME as _MODULE_MAP,  # local to avoid leaking name
    )
    module_name = _MODULE_MAP.get(name, name)

    argv_display = " ".join(_shellquote(a) for a in result.argv)
    return render_template(
        "_result.html",
        result=result,
        spec=spec,
        module_name=module_name,
        argv_display=argv_display,
    )


# ── Workspace routes ────────────────────────────────────────────────────────


@app.route("/projects")
def projects_list():
    """List all research projects."""
    return render_template(
        "projects.html",
        projects=projects_mod.list_projects(),
        flash_error=request.args.get("error"),
    )


@app.route("/projects/new", methods=["GET", "POST"])
def projects_new():
    """Create a new project."""
    if request.method == "POST":
        try:
            project = projects_mod.create_project(
                title=request.form.get("title", ""),
                research_question=request.form.get("research_question", ""),
                hypothesis=request.form.get("hypothesis", ""),
                keywords=request.form.get("keywords", ""),
                citation_style=request.form.get("citation_style", "APA"),
                supervisor_notes=request.form.get("supervisor_notes", ""),
                discipline=request.form.get("discipline", ""),
            )
            return redirect(url_for("projects_detail", slug=project.slug))
        except (ValueError, FileExistsError) as exc:
            return render_template(
                "project_form.html",
                project=None,
                flash_error=str(exc),
            )
    return render_template("project_form.html", project=None)


@app.route("/projects/<slug>", methods=["GET", "POST"])
def projects_detail(slug: str):
    """Edit an existing project."""
    project = projects_mod.get_project(slug)
    if project is None:
        return redirect(url_for("projects_list", error="Project not found"))

    if request.method == "POST":
        try:
            project = projects_mod.update_project(
                slug,
                research_question=request.form.get("research_question", ""),
                hypothesis=request.form.get("hypothesis", ""),
                keywords=request.form.get("keywords", ""),
                citation_style=request.form.get("citation_style", "APA"),
                supervisor_notes=request.form.get("supervisor_notes", ""),
                discipline=request.form.get("discipline", ""),
            )
        except (ValueError, FileNotFoundError) as exc:
            return render_template(
                "project_form.html",
                project=project,
                flash_error=str(exc),
                context_preview=projects_mod.project_context_block(project),
            )

    return render_template(
        "project_form.html",
        project=project,
        context_preview=projects_mod.project_context_block(project),
    )


@app.route("/projects/<slug>/delete", methods=["POST"])
def projects_delete(slug: str):
    projects_mod.delete_project(slug)
    return redirect(url_for("projects_list"))


@app.route("/projects/<slug>/activate", methods=["POST"])
def projects_activate(slug: str):
    """Mark a project as the active one (drives the dashboard banner and the
    Outline Recommender pre-fill)."""
    try:
        projects_mod.set_active_slug(slug)
    except FileNotFoundError:
        return redirect(url_for("projects_list", error="Project not found"))
    return redirect(request.referrer or url_for("projects_list"))


@app.route("/orchestration")
def orchestration_dashboard():
    """Model orchestration dashboard — totals, per-model, recent calls."""
    window = _safe_int(request.args.get("window"), 30)
    window = max(1, min(window, 365))
    data = telemetry_mod.collect(window_days=window)
    return render_template("orchestration.html", data=data)


@app.route("/prompts")
def prompts_page():
    """Browse the curated prompt library."""
    category = request.args.get("category") or None
    prompts = prompts_mod.list_prompts(category)
    return render_template(
        "prompts.html",
        prompts=prompts,
        categories=prompts_mod.categories_with_counts(),
        active_category=category,
    )


_DEFAULT_PEER_ROLES = ("structural", "methodology", "citation")


@app.route("/peer-review", methods=["GET", "POST"])
def peer_review_page():
    """Multi-model AI peer review."""
    roles = peer_review_mod.available_roles()
    projects = projects_mod.list_projects()
    draft = ""
    selected_roles = list(_DEFAULT_PEER_ROLES)
    model_overrides: dict[str, str] = {r.key: r.default_model for r in roles}
    synthesis_model = "claude"
    selected_project = ""
    report = None
    flash_error = None

    if request.method == "POST":
        draft = request.form.get("draft", "").strip()
        selected_roles = request.form.getlist("roles") or list(_DEFAULT_PEER_ROLES)
        synthesis_model = request.form.get("synthesis_model", "").strip() or None
        selected_project = request.form.get("project_slug", "").strip()
        model_overrides = {
            r.key: request.form.get(f"model_{r.key}", r.default_model) for r in roles
        }
        try:
            project_obj = (
                projects_mod.get_project(selected_project) if selected_project else None
            )
            report = peer_review_mod.run_peer_review(
                draft,
                roles=tuple(selected_roles),
                model_overrides=model_overrides,
                synthesis_model=synthesis_model or None,
                project=project_obj,
            )
        except Exception as exc:
            flash_error = str(exc)

    return render_template(
        "peer_review.html",
        roles=roles,
        models=MODELS,
        projects=projects,
        draft=draft,
        selected_roles=selected_roles,
        model_overrides=model_overrides,
        synthesis_model=synthesis_model or "",
        selected_project=selected_project,
        report=report,
        flash_error=flash_error,
    )


# ── Three-pane workspace ────────────────────────────────────────────────────


_QUICK_PROMPTS: tuple[tuple[str, str, str], ...] = (
    (
        "tighten",
        "Tighten prose, keep meaning",
        "Tighten the entire document for academic tone: remove filler, "
        "prefer concrete verbs, do not add new claims or citations, keep "
        "all existing references in place.",
    ),
    (
        "expand-methods",
        "Expand the Methods section",
        "Expand the Methods section with a brief sample-size justification "
        "and a paragraph on threats to validity. Use the selected source "
        "PDFs as evidence. Do not invent citations.",
    ),
    (
        "lit-summary",
        "Summarise selected PDFs into the Introduction",
        "Summarise the selected source PDFs into 2–3 paragraphs that fit "
        "at the end of the Introduction. Mark each claim with the source "
        "filename in brackets, e.g. [SourceA.pdf]. Do not invent results.",
    ),
    (
        "add-limitations",
        "Add a Limitations subsection to Discussion",
        "Add a `### Limitations` subsection at the end of the Discussion "
        "section with 3 honest limitations and how a follow-up could "
        "address each one. Do not weaken the main findings elsewhere.",
    ),
    (
        "abstract",
        "Draft an Abstract from the current document",
        "Rewrite the Abstract section based on what is currently in the "
        "rest of the document. Keep it under 250 words. Do not introduce "
        "claims that are not already supported elsewhere in the document.",
    ),
)


@app.route("/workspace")
def workspace_index():
    """Pick a project to open in the three-pane workspace."""
    return render_template(
        "workspace_index.html",
        projects=projects_mod.list_projects(),
    )


@app.route("/workspace/<slug>", methods=["GET", "POST"])
def workspace_detail(slug: str):
    """Three-pane workspace: project + PDFs (left), document + prompt (center), telemetry (right)."""
    project = projects_mod.get_project(slug)
    if project is None:
        return redirect(url_for("workspace_index"))

    try:
        document = doc_mod.load(slug)
    except FileNotFoundError:
        return redirect(url_for("workspace_index"))

    pdfs = library_mod.list_pdfs()
    pdf_root = str(library_mod.configured_root())

    outcome = None
    flash_error = None
    pending_instruction = ""
    selected_model = "sonnet"

    if request.method == "POST":
        instruction = request.form.get("instruction", "").strip()
        pending_instruction = instruction
        selected_model = request.form.get("model", selected_model)
        sources_csv = request.form.get("sources_csv", "")
        sources = tuple(
            line.strip() for line in sources_csv.splitlines() if line.strip()
        )

        if not instruction:
            flash_error = "Tell the AI what to change before applying an edit."
        else:
            outcome = editor_mod.apply_edit(
                current_document=document.content,
                instruction=instruction,
                sources=sources,
                model=selected_model,
                project=project,
            )
            if outcome.error:
                flash_error = outcome.error
            elif outcome.new_document.strip():
                document = doc_mod.save(slug, outcome.new_document)

    quick_prompts = [(slug_, label) for slug_, label, _ in _QUICK_PROMPTS]
    quick_prompts_map = {slug_: body for slug_, _, body in _QUICK_PROMPTS}

    telemetry_data = telemetry_mod.collect(window_days=30, recent_limit=8)

    return render_template(
        "workspace.html",
        project=project,
        document=document,
        pdfs=pdfs,
        pdf_root=pdf_root,
        models=MODELS,
        selected_model=selected_model,
        outcome=outcome,
        flash_error=flash_error,
        pending_instruction=pending_instruction,
        quick_prompts=quick_prompts,
        quick_prompts_map=quick_prompts_map,
        telemetry=telemetry_data,
    )


@app.route("/workspace/<slug>/save", methods=["POST"])
def workspace_save(slug: str):
    """Manual save from the editor textarea."""
    if projects_mod.get_project(slug) is None:
        return redirect(url_for("workspace_index"))
    content = request.form.get("content", "")
    doc_mod.save(slug, content)
    return redirect(url_for("workspace_detail", slug=slug))


@app.route("/workspace/<slug>/undo", methods=["POST"])
def workspace_undo(slug: str):
    """Revert the last save (text edit or AI edit)."""
    if projects_mod.get_project(slug) is None:
        return redirect(url_for("workspace_index"))
    doc_mod.undo(slug)
    return redirect(url_for("workspace_detail", slug=slug))


@app.route("/defense", methods=["GET", "POST"])
def defense_page():
    """Thesis defense simulator."""
    personas = defense_mod.available_personas()
    projects = projects_mod.list_projects()
    material = ""
    selected_persona = "strict-reviewer"
    selected_model = "claude"
    count = 8
    selected_project = ""
    result = None
    flash_error = None

    if request.method == "POST":
        material = request.form.get("material", "").strip()
        selected_persona = request.form.get("persona", selected_persona)
        selected_model = request.form.get("model", selected_model)
        count = _safe_int(request.form.get("count"), count)
        selected_project = request.form.get("project_slug", "").strip()
        try:
            project_obj = (
                projects_mod.get_project(selected_project) if selected_project else None
            )
            result = defense_mod.run_defense(
                material,
                persona=selected_persona,
                model=selected_model,
                count=count,
                project=project_obj,
            )
        except Exception as exc:
            flash_error = str(exc)

    return render_template(
        "defense.html",
        personas=personas,
        models=MODELS,
        projects=projects,
        material=material,
        selected_persona=selected_persona,
        selected_model=selected_model,
        count=count,
        selected_project=selected_project,
        result=result,
        flash_error=flash_error,
    )


# ── Providers + Settings routes ───────────────────────────────────────────────


@app.route("/providers")
def providers_page():
    """Show API-key and CLI provider health; allow per-provider test runs."""
    return render_template(
        "providers.html",
        cli_providers=cli_provider_status(),
        api_providers=api_provider_status(),
        models=MODELS,
    )


@app.route("/providers/test", methods=["POST"])
def providers_test():
    """HTMX endpoint: round-trip a tiny prompt through the chosen alias."""
    alias = request.form.get("alias", "").strip()
    result = test_provider(alias)
    return render_template("_provider_test.html", result=result)


@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    """Read-only secret status + editable paths/CLI config written back to .env."""
    flash_error = None
    flash_ok = None
    if request.method == "POST":
        try:
            path = settings_store.save(request.form.to_dict())
            flash_ok = f"Saved to {path}. Restart ra-web for changes to take full effect."
        except (ValueError, OSError) as exc:
            flash_error = str(exc)

    return render_template(
        "settings.html",
        secrets=settings_store.secret_status(),
        fields=settings_store.editable_values(),
        env_file=str(settings_store.env_path()),
        flash_error=flash_error,
        flash_ok=flash_ok,
    )


def _shellquote(s: str) -> str:
    """Minimal shell-safe quoting for display only."""
    if not s:
        return "''"
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_./=:,")
    if all(c in safe_chars for c in s):
        return s
    return "'" + s.replace("'", "'\\''") + "'"


def _cli() -> None:
    """Console-script entry point.

    Configurable via env vars:
        RA_HOST       (default 127.0.0.1)
        RA_PORT       (default 5050)
        FLASK_DEBUG=1 to enable debug mode
    """
    host = os.environ.get("RA_HOST", "127.0.0.1")
    port = int(os.environ.get("RA_PORT", "5050"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host=host, port=port)


if __name__ == "__main__":
    _cli()
