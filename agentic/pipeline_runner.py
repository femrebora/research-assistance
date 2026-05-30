"""pipeline_runner.py — step-by-step pipeline execution for the interactive UI.

Unlike the LangGraph orchestrator, this runs agents individually with explicit
pauses. State is persisted to disk after each step. Intended to be called from
Flask routes (sync for single-agent calls, background thread for multi-agent
sequences).

Key flows:
  run_generate(job_id)          — code_analyst → writer, then PAUSE at draft_ready
  apply_section_feedback(job_id, section_key, feedback)
                                — targeted rewriter call for one section
  run_assess_revise(job_id)     — assessor → rewriter loop, streaming via SSE
  run_finalize(job_id)          — plagiarism → figures → supervisor → complete
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from agentic.section_parser import parse_sections
from agentic.state_store import (
    append_event,
    load_state,
    save_state,
)


def run_generate(job_id: str):
    """Run code_analyst → writer. Saves state + emits events after each step.

    Called in a background thread from the Flask route.
    """
    state = load_state(job_id)
    try:
        state["started_at"] = __import__("time").time()

        # ── Step 1: Code Analyst ────────────────────────────────────────
        append_event(job_id, {
            "type": "agent", "agent": "Code Analyst", "message": "Analyzing codebase..."
        })
        save_state(job_id, {"status": "analyzing"})

        if state["mode"] == "review":
            from agentic.agents.literature_researcher import run_literature_researcher
            delta = run_literature_researcher(state)
        else:
            from agentic.agents.code_analyst import run_code_analyst
            delta = run_code_analyst(state)

        state.update(delta)
        _merge_agent_calls(state, delta)
        save_state(job_id, {
            "technical_report": state.get("technical_report"),
            "agent_calls": state.get("agent_calls", []),
            "status": "writing",
        })
        append_event(job_id, {
            "type": "agent", "agent": "Code Analyst",
            "message": f"Done: {len(state.get('technical_report', ''))} chars"
        })

        # ── Step 2a: Outline (RA) ───────────────────────────────────────
        try:
            append_event(job_id, {
                "type": "agent", "agent": "Outline", "message": "Planning structure..."
            })
            from agentic.bridge import call_agent
            from research_assistant.writing.outline_recommender import build_structure_prompt
            topic = state.get("user_summary", "") or state.get("topic", "")
            prompt = build_structure_prompt(topic=topic, paper_type_key="imrad",
                                             discipline="computational", audience="academic", target_words=5000)
            result = call_agent(prompt=prompt, model="claude", temperature=0.3,
                                system="You are a scientific editor. Output the outline only.")
            state["outline"] = result.get("text", "")
            _merge_agent_calls(state, {"agent_calls": [{
                "agent": "outline", "model": "claude",
                "input_tokens": result.get("input_tokens", 0),
                "output_tokens": result.get("output_tokens", 0),
                "cost": result.get("cost", 0),
            }]})
            append_event(job_id, {
                "type": "agent", "agent": "Outline",
                "message": f"Done: {len(state['outline'])} chars"
            })
        except Exception:
            import sys as _sys
            import traceback as _tb
            print("ERROR in outline/paraphrase:", file=_sys.stderr)
            _tb.print_exc(file=_sys.stderr)

        # ── Step 2b: Writer ──────────────────────────────────────────────
        append_event(job_id, {
            "type": "agent", "agent": "Writer", "message": "Drafting paper..."
        })

        from agentic.agents.writer import run_writer
        delta = run_writer(state)
        state.update(delta)
        _merge_agent_calls(state, delta)

        # ── Step 2c: Paraphrase polish (RA) ─────────────────────────────
        try:
            append_event(job_id, {
                "type": "agent", "agent": "Paraphrase", "message": "Polishing prose..."
            })
            from research_assistant.writing.paraphrase import run_paraphrase_pipeline
            draft = state.get("draft", "")
            if len(draft) > 500:
                results = run_paraphrase_pipeline(
                    brief="", writer=None, paraphraser="claude", checker="claude",
                    existing_draft=draft, temperature=0.3)
                if results and results[-1].output:
                    state["draft"] = results[-1].output
                    state["paraphrase_applied"] = True
            append_event(job_id, {
                "type": "agent", "agent": "Paraphrase", "message": "Done"
            })
        except Exception:
            import sys as _sys
            import traceback as _tb
            print("ERROR in outline/paraphrase:", file=_sys.stderr)
            _tb.print_exc(file=_sys.stderr)

        # Parse into sections and score them
        sections = parse_sections(state.get("draft", ""))
        _score_sections(sections)
        save_state(job_id, {
            "draft": state.get("draft"),
            "outline": state.get("outline"),
            "sections": sections,
            "agent_calls": state.get("agent_calls", []),
            "status": "draft_ready",
        })
        append_event(job_id, {
            "type": "agent", "agent": "Writer",
            "message": f"Draft: {len(state.get('draft', ''))} chars"
        })
        append_event(job_id, {
            "type": "draft_ready",
            "sections": [{"key": s["key"], "heading": s["heading"],
                          "version": s["version"]} for s in sections]
        })

    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        save_state(job_id, {"status": "error", "error": str(e)})
        append_event(job_id, {"type": "error", "message": str(e)})


def apply_section_feedback(job_id: str, section_key: str, feedback: str) -> dict:
    """Revise only the target section — sends just that section to the LLM,
    gets back the revised content, and splices it into the full draft.
    """
    state = load_state(job_id)
    sections = state.get("sections") or []
    section = _find_section(sections, section_key)
    if not section:
        return {"error": f"Section '{section_key}' not found"}

    full_draft = state.get("draft", "")

    prompt = _build_section_feedback_prompt(
        full_draft, section_key, section["content"], feedback)

    result = _call_rewriter(prompt, state)
    if result.get("error"):
        return {"error": result["error"]}

    revised = result.get("section_text", "")
    # Guard against meta-commentary / refusal responses from the LLM
    if not revised or len(revised) < 50:
        return {"error": "Revision returned empty or too short — draft unchanged"}
    if revised.startswith("# Cannot") or "No Manuscript" in revised or "not a paper" in revised.lower():
        return {"error": "LLM refused to revise — draft unchanged"}

    revised = _restore_heading(revised, section["heading"])

    # Save old version before replacing
    history = state.get("section_history") or {}
    if section_key not in history:
        history[section_key] = []
    history[section_key].append(section["content"])
    if len(history[section_key]) > 10:
        history[section_key] = history[section_key][-10:]

    # Safely splice revised section into draft via section boundaries
    from agentic.section_parser import rebuild_draft, update_section
    update_section(sections, section_key, revised)
    new_draft = rebuild_draft(sections)

    # Re-parse and re-score
    new_sections = parse_sections(new_draft)
    _score_sections(new_sections)
    for ns in new_sections:
        old = _find_section(sections, ns["key"])
        if old:
            ns["version"] = old["version"] + 1 if ns["key"] == section_key else old["version"]
            ns["critique"] = old.get("critique")
            ns["score"] = old.get("score")
            # ai_score is set fresh by _score_sections — don't overwrite
            # Clear zerogpt score on revised section (needs re-check), preserve on others
            if ns["key"] != section_key:
                ns["zerogpt_score"] = old.get("zerogpt_score")

    feedback_log = state.get("feedback_log") or []
    feedback_log.append({
        "section_key": section_key,
        "feedback": feedback[:500],
        "time": __import__("time").time(),
    })

    state.update({
        "draft": new_draft,
        "sections": new_sections,
        "section_history": history,
        "agent_calls": state.get("agent_calls", []) + result.get("agent_calls", []),
        "feedback_log": feedback_log,
        "text_rewrite_count": state.get("text_rewrite_count", 0) + 1,
    })
    save_state(job_id, state)
    append_event(job_id, {
        "type": "feedback_applied",
        "section_key": section_key,
        "updated_section": _find_section(new_sections, section_key),
    })

    return state


def run_assess_revise(job_id: str):
    """Run assessor → rewriter loop. Background thread, streams via SSE.

    Stops when all sections score >= 7 or max_rewrites reached.
    """
    state = load_state(job_id)
    max_rewrites = state.get("max_rewrites", 3)
    try:
        for iteration in range(1, max_rewrites + 1):
            save_state(job_id, {"status": "assessing"})
            append_event(job_id, {
                "type": "status",
                "message": f"Assess & Revise loop {iteration}/{max_rewrites}..."
            })

            # Assess (PF + RA Peer Review)
            from agentic.agents.assessor import run_assessor
            delta = run_assessor(state)
            state.update(delta)
            _merge_agent_calls(state, delta)
            assessment = (state.get("assessment") or {})

            # RA Peer Review (runs in parallel with assessor result already available)
            try:
                from research_assistant.workspace.peer_review import run_peer_review
                peer = run_peer_review(state.get("draft", ""),
                                        roles=("structural", "methodology", "citation"),
                                        synthesis_model=None, temperature=0.3, max_workers=3)
                # Parse per-role feedback into state
                peer_data = {}
                for role in peer.reviews:
                    peer_data[role.role] = {
                        "score": getattr(role, "score", None),
                        "feedback": getattr(role, "text", "")[:1000],
                    }
                state["peer_review"] = peer_data
                if peer.synthesis:
                    state["peer_review_synthesis"] = peer.synthesis
            except Exception:
                import traceback as _tb2
            _tb2.print_exc()

            append_event(job_id, {
                "type": "assessment_ready",
                "assessment": assessment,
                "peer_review": state.get("peer_review"),
                "iteration": iteration,
            })

            # Check scores
            low = {k: v["score"] for k, v in assessment.items()
                   if isinstance(v, dict) and v.get("score", 10) < 7}
            if not low:
                append_event(job_id, {"type": "status",
                    "message": "All sections >= 7/10 — passed!"})
                break

            append_event(job_id, {
                "type": "status",
                "message": f"Low scores: {' '.join(f'{k}={v}' for k,v in low.items())}"
            })

            # Rewrite
            if iteration < max_rewrites:
                save_state(job_id, {"status": "rewriting"})
                append_event(job_id, {
                    "type": "agent", "agent": "Rewriter",
                    "message": f"Revision #{iteration}..."
                })
                from agentic.agents.rewriter import run_rewriter
                delta = run_rewriter(state)
                state.update(delta)
                _merge_agent_calls(state, delta)
                state["text_rewrite_count"] = iteration
                sections = parse_sections(state.get("draft", ""))
                save_state(job_id, {
                    "draft": state.get("draft"),
                    "sections": sections,
                    "assessment": assessment,
                    "text_rewrite_count": iteration,
                    "agent_calls": state.get("agent_calls", []),
                })
            else:
                append_event(job_id, {
                    "type": "status",
                    "message": f"Max rewrites ({max_rewrites}) reached"
                })

        # Re-parse final draft
        sections = parse_sections(state.get("draft", ""))
        # Apply assessment scores to sections
        for s in sections:
            sec_assess = assessment.get(s["key"])
            if isinstance(sec_assess, dict):
                s["score"] = sec_assess.get("score")
                s["ai_score"] = sec_assess.get("ai_score")
                s["critique"] = sec_assess.get("critique")

        save_state(job_id, {
            "assessment": assessment,
            "sections": sections,
            "status": "draft_ready",
        })
        append_event(job_id, {
            "type": "assessment_ready",
            "assessment": assessment,
            "sections": [{"key": s["key"], "score": s.get("score")} for s in sections],
        })

    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        save_state(job_id, {"status": "error", "error": str(e)})
        append_event(job_id, {"type": "error", "message": str(e)})


def run_finalize(job_id: str):
    """Run plagiarism → figures → supervisor. Background thread, SSE streaming."""
    state = load_state(job_id)
    try:
        save_state(job_id, {"status": "finalizing"})

        # PF Plagiarism
        append_event(job_id, {
            "type": "agent", "agent": "Plagiarism Check",
            "message": "Checking originality..."
        })
        from agentic.agents.plagiarism_check import run_plagiarism_check
        delta = run_plagiarism_check(state)
        state.update(delta)
        _merge_agent_calls(state, delta)

        # RA Claim Verify
        try:
            append_event(job_id, {
                "type": "agent", "agent": "Claim Verify",
                "message": "Verifying claims..."
            })
            import re

            from research_assistant.verification.claim_verify import verify_claim
            draft = state.get("draft", "")
            claims = [s.strip() for s in re.split(r'(?<=[.!?])\s+', draft)
                      if len(s.strip()) > 80 and any(w in s.lower() for w in
                        ['kj/mol','kcal','rmsd','binding','mutation','inhibit','increase','decrease',
                         'show','find','result','observe','demonstrate'])]
            verified = []
            for claim in claims[:15]:
                try:
                    v = verify_claim(claim, lambda q, k=3: [], model="claude", k=3, threshold=0.5)
                    verified.append({"claim": claim[:200], "verdict": v.verdict if hasattr(v,'verdict') else "?"})
                except Exception:
                    pass
            state["claim_verify"] = verified
        except Exception:
            import sys as _sys
            import traceback as _tb
            print("ERROR in outline/paraphrase:", file=_sys.stderr)
            _tb.print_exc(file=_sys.stderr)

        # RA External Match
        try:
            append_event(job_id, {
                "type": "agent", "agent": "External Match",
                "message": "Checking against literature..."
            })
            from research_assistant.verification.external_match import cached_search
            matches = []
            topic = state.get("user_summary", "")[:200]
            if topic:
                results = cached_search("openalex", topic, limit=3)
                for r in (results or [])[:3]:
                    matches.append({"title": r.get("title", ""), "year": r.get("year", ""),
                                    "similarity": round(r.get("score", 0), 2)})
            state["external_matches"] = matches
        except Exception:
            import sys as _sys
            import traceback as _tb
            print("ERROR in outline/paraphrase:", file=_sys.stderr)
            _tb.print_exc(file=_sys.stderr)

        # RA Disclose
        try:
            from research_assistant.writing.disclose import aggregate, load_logs
            records = load_logs(since=None, until=None)
            state["disclosure"] = aggregate(records) if records else {}
        except Exception:
            pass

        save_state(job_id, {
            "originality_score": state.get("originality_score"),
            "claim_verify": state.get("claim_verify"),
            "external_matches": state.get("external_matches"),
            "disclosure": state.get("disclosure"),
            "agent_calls": state.get("agent_calls", []),
        })
        append_event(job_id, {
            "type": "status",
            "message": f"Originality: {state.get('originality_score', {}).get('originality_pct', '?')}%. "
                       f"Claims verified: {len(state.get('claim_verify', []))}"
        })

        # Generate figures from paper data
        append_event(job_id, {
            "type": "agent", "agent": "Figure Gen",
            "message": "Generating charts..."
        })
        figures_dir = Path(state["output_dir"]) / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        figures = _generate_figures(state, figures_dir)
        save_state(job_id, {"figures": figures})
        append_event(job_id, {
            "type": "figures_ready",
            "figures": figures,
        })

        # Replace [FIG ...] placeholders with markdown image references
        import re as _re
        draft = state.get("draft", "")
        structured_pattern = _re.compile(r'\[FIG\s+\w+\s*\|[^\]]+\]')
        fig_list = state.get("figures") or figures
        fig_idx = 0
        def _replace_fig(m):
            nonlocal fig_idx
            if fig_idx < len(fig_list):
                fname = f"figures/figure_{fig_idx+1}.png"
                fig_idx += 1
                return f"![Figure {fig_idx}]({fname})"
            return m.group(0)
        draft = structured_pattern.sub(_replace_fig, draft)
        # Also replace legacy [FIGURE: ...] placeholders
        draft = _re.sub(r'\[FIGURE:\s*[^\]]+\]', _replace_fig, draft)

        # Write draft to output dir
        out_dir = Path(state["output_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "paper.md").write_text(draft, encoding="utf-8")
        (out_dir / "assessment.json").write_text(
            __import__("json").dumps((state.get("assessment") or {}), indent=2),
            encoding="utf-8")
        (out_dir / "originality.json").write_text(
            __import__("json").dumps(state.get("originality_score", {}), indent=2),
            encoding="utf-8")

        save_state(job_id, {
            "agent_calls": state.get("agent_calls", []),
            "status": "complete",
            "completed_at": __import__("time").time(),
        })

        cost = sum(c.get("cost", 0) or 0 for c in state.get("agent_calls", []))
        append_event(job_id, {
            "type": "complete",
            "results": {
                "output_dir": str(out_dir),
                "agent_calls": len(state.get("agent_calls", [])),
                "text_rewrites": state.get("text_rewrite_count", 0),
                "estimated_cost": round(cost, 4),
            }
        })

    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        save_state(job_id, {"status": "error", "error": str(e)})
        append_event(job_id, {"type": "error", "message": str(e)})


# ── helpers ──────────────────────────────────────────────────────────────

def revert_section(job_id: str, section_key: str) -> dict:
    """Revert a section to its previous version."""
    state = load_state(job_id)
    history = state.get("section_history") or {}
    versions = history.get(section_key) or []
    if not versions:
        return {"error": "No previous version to revert to"}

    sections = state.get("sections") or []
    section = _find_section(sections, section_key)
    if not section:
        return {"error": f"Section '{section_key}' not found"}

    # Pop last version from history
    old_content = versions.pop()

    # Swap: old becomes current
    history[section_key] = versions
    if len(versions) >= 10:
        history[section_key] = versions[-10:]

    from agentic.section_parser import rebuild_draft as _rebuild
    from agentic.section_parser import update_section as _update
    _update(sections, section_key, old_content)
    new_draft = _rebuild(sections)
    new_sections = parse_sections(new_draft)
    _score_sections(new_sections)
    for ns in new_sections:
        orig = _find_section(sections, ns["key"])
        if orig:
            ns["version"] = orig.get("version", 0) + 1 if ns["key"] == section_key else orig.get("version", 0)
            ns["zerogpt_score"] = orig.get("zerogpt_score")

    state.update({
        "draft": new_draft,
        "sections": new_sections,
        "section_history": history,
        "text_rewrite_count": state.get("text_rewrite_count", 0) + 1,
    })
    save_state(job_id, state)
    return {"status": "ok", "section_key": section_key}


def _score_sections(sections: list[dict]):
    """Quick mechanical AI detection on each section. Instant, no API call.
    Use zerogpt_check_section() for real ZeroGPT scores (slower but accurate).
    """
    try:
        from agentic.quick_ai_score import score_text
        for s in sections:
            if s["key"] == "preamble" or len(s.get("content", "")) < 100:
                continue
            result = score_text(s["content"])
            s["ai_score"] = round(result["overall_score"] * 10)
            if "zerogpt_score" not in s:
                s["zerogpt_score"] = None
    except Exception:
        import traceback
        traceback.print_exc()


def zerogpt_check_section(job_id: str, section_key: str) -> dict:
    """Run actual ZeroGPT check on one section and update state."""
    from agentic.mcp_servers.zerogpt_server import _check_via_playwright

    state = load_state(job_id)
    sections = state.get("sections") or []
    section = _find_section(sections, section_key)
    if not section:
        return {"error": f"Section '{section_key}' not found"}

    try:
        result = _check_via_playwright(section["content"][:5000])
        score = round(result.get("ai_probability_pct", 0))
    except Exception:
        import traceback
        traceback.print_exc()
        return {"error": "ZeroGPT check failed — Playwright error"}

    section["zerogpt_score"] = score
    save_state(job_id, {"sections": sections})
    return {"section_key": section_key, "zerogpt_score": score}


def _restore_heading(text: str, heading: str) -> str:
    """Ensure the section text starts with its heading."""
    text = text.strip()
    if text.startswith("#"):
        return text
    return heading + "\n" + text


def _find_section(sections: list[dict], key: str) -> dict | None:
    for s in sections:
        if s.get("key") == key:
            return s
    return None


def _parse_structured_fig(draft: str, figures_dir: Path, start_idx: int) -> tuple[list[dict], int]:
    """Parse [FIG type|title|cats|series] placeholders and render charts."""
    import json
    import re

    from agentic.mcp_servers.chart_server import (
        bar_chart,
        grouped_bar_chart,
        line_chart,
        pie_chart,
        radar_chart,
        timeline_chart,
    )
    figures = []
    idx = start_idx
    for ftype, title, cats_str, series_str in re.findall(
            r'\[FIG\s+(\w+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*(.+?)\]', draft):
        try:
            path = str(figures_dir / f"figure_{idx+1}.png")
            title = title.strip()
            ftype = ftype.strip().lower()
            cats = [c.strip() for c in cats_str.split(",")]
            idx += 1
            if ftype == "bar":
                bar_chart(json.dumps({"categories": cats, "values": [float(v.strip()) for v in series_str.split(",")]}),
                          title=title, output=path, theme="scientific")
            elif ftype == "grouped_bar":
                series = {}
                for p in series_str.split("|"):
                    n, vs = p.split(":", 1)
                    series[n.strip()] = [float(v.strip()) for v in vs.split(",")]
                grouped_bar_chart(json.dumps({"categories": cats, "series": series}), title=title, output=path, theme="scientific")
            elif ftype == "line":
                x = [int(v) if v.strip().isdigit() else v.strip() for v in cats_str.split(",")]
                series = {}
                for p in series_str.split("|"):
                    n, vs = p.split(":", 1)
                    series[n.strip()] = [float(v.strip()) for v in vs.split(",")]
                line_chart(json.dumps({"x": x, "series": series}), title=title, output=path, theme="scientific")
            elif ftype == "pie":
                segments = []
                for s in series_str.split(","):
                    label, val = s.rsplit(":", 1)
                    segments.append({"label": label.strip(), "value": float(val.strip())})
                pie_chart(json.dumps({"segments": segments}), title=title, output=path, theme="scientific")
            elif ftype in ("radar",):
                series = []
                for p in series_str.split("|"):
                    n, vs = p.split(":", 1)
                    series.append({"label": n.strip(), "values": [float(v.strip()) for v in vs.split(",")]})
                radar_chart(json.dumps({"categories": cats, "series": series}), title=title, output=path, theme="scientific")
            elif ftype == "timeline":
                events = []
                for e in series_str.split("|"):
                    date, label_text = e.split(":", 1)
                    events.append({"date": date.strip(), "label": label_text.strip()})
                timeline_chart(json.dumps({"events": events}), title=title, output=path, theme="scientific")
            else:
                idx -= 1
                continue
            figures.append({"index": idx - 1, "title": title, "png_path": path})
        except Exception:
            import sys as _sys
            import traceback as _tb
            print("ERROR in outline/paraphrase:", file=_sys.stderr)
            _tb.print_exc(file=_sys.stderr)
            idx -= 1
    return figures, idx


def _generate_figures(state: dict, figures_dir: Path) -> list[dict]:
    """Generate charts from structured [FIG ...] or legacy [FIGURE: ...] placeholders."""
    import json
    import re

    from agentic.bridge import call_agent
    from agentic.mcp_servers.chart_server import (
        bar_chart,
        grouped_bar_chart,
        line_chart,
        pie_chart,
    )
    draft = state.get("draft", "")

    # Phase 1: structured [FIG type|title|cats|series] — no LLM needed
    figures, idx = _parse_structured_fig(draft, figures_dir, 0)

    # Phase 2: legacy [FIGURE: description] — LLM-driven
    legacy = re.findall(r'\[FIGURE:\s*(.*?)\]', draft)
    # Filter out descriptions already covered by structured figs
    remaining = [d for d in legacy if not any(
        d[:30] in s for s in re.findall(r'\[FIG\s+\w+\|([^|]+)', draft))]
    if remaining:
        tech = state.get("technical_report", "")
        prompt = f"""Extract real data from this paper and generate chart specs.
Technical report: {tech[:3000]}
Paper: {draft[:4000]}
Descriptions: {chr(10).join(f'{i+1}. {d}' for i, d in enumerate(remaining))}

Output JSON: {{"figures":[{{"type":"bar|grouped_bar|line|pie|radar|timeline","title":"...","categories":[...],"values":[...],"series":{{...}}}}]}}
Use ONLY numbers from the data. JSON only."""

        result = call_agent(prompt=prompt, model="claude", temperature=0.2)
        try:
            text = result.get("text", "")
            if "{" in text:
                text = text[text.find("{"):text.rfind("}")+1]
            for fig in json.loads(text).get("figures", []):
                try:
                    path = str(figures_dir / f"figure_{idx+1}.png")
                    ftype, title = fig.get("type", "bar"), fig.get("title", f"Figure {idx+1}")
                    if ftype == "bar":
                        bar_chart(json.dumps({"categories": fig["categories"], "values": fig["values"]}), title=title, output=path, theme="scientific")
                    elif ftype == "grouped_bar":
                        grouped_bar_chart(json.dumps({"categories": fig["categories"], "series": fig["series"]}), title=title, output=path, theme="scientific")
                    elif ftype == "line":
                        line_chart(json.dumps({"x": fig["x"], "series": fig["series"]}), title=title, output=path, theme="scientific")
                    elif ftype == "pie":
                        pie_chart(json.dumps({"segments": fig["segments"]}), title=title, output=path, theme="scientific")
                    figures.append({"index": idx, "title": title, "png_path": path})
                    idx += 1
                except Exception:
                    import traceback as _tb2
            _tb2.print_exc()
        except Exception:
            import sys as _sys
            import traceback as _tb
            print("ERROR in outline/paraphrase:", file=_sys.stderr)
            _tb.print_exc(file=_sys.stderr)
    return figures


def _merge_agent_calls(state: dict, delta: dict):
    """Append agent_calls from delta to state."""
    existing = list(state.get("agent_calls") or [])
    new_calls = delta.get("agent_calls") or []
    existing.extend(new_calls)
    state["agent_calls"] = existing


def _call_rewriter(prompt: str, state: dict) -> dict:
    """Call the rewriter on a single section. Returns {section_text, agent_calls}."""
    from agentic.bridge import call_agent

    SYSTEM = (
        "You are an expert academic editor. Revise the text based on the user's "
        "feedback. Output ONLY the revised section content — no preamble, no "
        "commentary, no markdown fences. Start directly with the section text."
    )

    # Prefer Claude CLI (key is set), DeepSeek as fallback
    import os
    if os.getenv("ANTHROPIC_AUTH_TOKEN", "").startswith("sk-"):
        result = call_agent(prompt=prompt, model="claude", system=SYSTEM, temperature=0.4)
    elif os.getenv("DEEPSEEK_API_KEY", "").startswith("sk-"):
        result = call_agent(prompt=prompt, model="deepseek", system=SYSTEM, temperature=0.4)
    else:
        return {"error": "No API key — set ANTHROPIC_AUTH_TOKEN or DEEPSEEK_API_KEY"}

    text = result.get("text", "")
    if "Not logged in" in text or "Please run" in text or len(text) < 50:
        return {"error": "Agent auth failed — draft unchanged"}

    return {
        "section_text": text.strip(),
        "agent_calls": [{
            "agent": "rewriter",
            "model": result.get("model", "unknown"),
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "cost": result.get("cost", 0),
        }],
    }


def _build_section_feedback_prompt(draft: str, section_key: str,
                                    section_content: str, feedback: str) -> str:
    """Build a prompt to rewrite just one section. Includes brief context."""
    return f"""## Context
You are revising the **{section_key}** section of an academic paper. Here is the section content:

{section_content[:4000]}

## User Feedback
{feedback}

## Instructions
Rewrite this section based on the feedback. Output ONLY the revised section content — no preamble, no "Here's the revised version", no markdown code fences. Start directly with the section text. Preserve all technical data, citations, numbers, and figures."""
