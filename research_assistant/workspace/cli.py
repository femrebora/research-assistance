"""Click-based CLI wrappers around the workspace features.

These map onto entry points declared in ``pyproject.toml`` so users can run
``ra-project``, ``ra-orchestration``, ``ra-prompts``, ``ra-peer-review``,
and ``ra-defense`` without booting the Flask UI.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from research_assistant.workspace import defense as defense_mod
from research_assistant.workspace import peer_review as peer_review_mod
from research_assistant.workspace import projects as projects_mod
from research_assistant.workspace import prompts_library as prompts_mod
from research_assistant.workspace import telemetry as telemetry_mod

# ── ra-project ──────────────────────────────────────────────────────────────


@click.group(help="Manage per-project research context.")
def project_main() -> None:
    pass


@project_main.command("list", help="List all projects.")
def _project_list() -> None:
    items = projects_mod.list_projects()
    if not items:
        click.echo("No projects yet. Use `ra-project create`.")
        return
    for p in items:
        click.echo(f"{p.slug:30s}  {p.title}")


@project_main.command("show", help="Show a project's context block.")
@click.argument("slug")
def _project_show(slug: str) -> None:
    project = projects_mod.get_project(slug)
    if project is None:
        click.echo(f"Project '{slug}' not found.", err=True)
        sys.exit(1)
    click.echo(projects_mod.project_context_block(project))


@project_main.command("create", help="Create a new project from a YAML/JSON file or flags.")
@click.option("--title", required=True)
@click.option("--question", default="", help="Research question")
@click.option("--hypothesis", default="")
@click.option("--keywords", default="", help="Comma-separated keywords")
@click.option("--style", "citation_style", default="APA")
@click.option("--discipline", default="")
@click.option("--notes", "supervisor_notes", default="")
def _project_create(
    title: str,
    question: str,
    hypothesis: str,
    keywords: str,
    citation_style: str,
    discipline: str,
    supervisor_notes: str,
) -> None:
    try:
        project = projects_mod.create_project(
            title=title,
            research_question=question,
            hypothesis=hypothesis,
            keywords=keywords,
            citation_style=citation_style,
            discipline=discipline,
            supervisor_notes=supervisor_notes,
        )
    except (ValueError, FileExistsError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    click.echo(f"Created project '{project.slug}'.")


@project_main.command("delete", help="Delete a project.")
@click.argument("slug")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def _project_delete(slug: str, yes: bool) -> None:
    if not yes:
        click.confirm(f"Delete project '{slug}'?", abort=True)
    if projects_mod.delete_project(slug):
        click.echo("Deleted.")
    else:
        click.echo("Nothing to delete.", err=True)


# ── ra-orchestration ────────────────────────────────────────────────────────


@click.command(help="Show model orchestration totals from the AI call logs.")
@click.option("--window", default=30, type=int, help="Window in days.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
def orchestration_main(window: int, as_json: bool) -> None:
    data = telemetry_mod.collect(window_days=window)
    if as_json:
        payload = {
            "total_calls": data.total_calls,
            "total_input_tokens": data.total_input_tokens,
            "total_output_tokens": data.total_output_tokens,
            "total_cost": data.total_cost,
            "per_model": [
                {
                    "alias": m.alias,
                    "calls": m.calls,
                    "input_tokens": m.input_tokens,
                    "output_tokens": m.output_tokens,
                    "cost": m.cost,
                    "last_used": m.last_used,
                }
                for m in data.per_model
            ],
        }
        click.echo(json.dumps(payload, indent=2))
        return
    click.echo(f"Window: last {window} days  ·  Logs: {data.log_dir}")
    click.echo(
        f"Calls: {data.total_calls}  |  "
        f"Input: {data.total_input_tokens:,}  |  "
        f"Output: {data.total_output_tokens:,}  |  "
        f"Cost: ${data.total_cost:.4f}"
    )
    click.echo("")
    click.echo(f"{'model':<14}{'calls':>8}{'in':>14}{'out':>14}{'cost':>14}")
    click.echo("-" * 64)
    for m in data.per_model:
        click.echo(
            f"{m.alias:<14}{m.calls:>8}{m.input_tokens:>14,}"
            f"{m.output_tokens:>14,}{m.cost:>14.4f}"
        )


# ── ra-prompts ──────────────────────────────────────────────────────────────


@click.command(help="List or print prompts from the curated library.")
@click.option("--category", default=None, help="Filter to one category.")
@click.option("--slug", default=None, help="Print the full body of a single prompt.")
def prompts_main(category: str | None, slug: str | None) -> None:
    if slug:
        p = prompts_mod.get_prompt(slug)
        if p is None:
            click.echo(f"Prompt '{slug}' not found.", err=True)
            sys.exit(1)
        click.echo(p.body)
        return
    items = prompts_mod.list_prompts(category)
    for p in items:
        click.echo(f"{p.slug:32s}  [{p.category:18s}]  {p.title}")


# ── ra-peer-review ──────────────────────────────────────────────────────────


@click.command(help="Run AI peer review on a draft file.")
@click.argument("draft_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--role",
    "roles",
    multiple=True,
    default=("structural", "methodology", "citation"),
    help="Reviewer role keys. Repeatable.",
)
@click.option("--model", "model_overrides", multiple=True, help="role=alias mappings.")
@click.option("--synthesis", default="claude", help="Synthesis model alias or 'none'.")
@click.option("--project", "project_slug", default="", help="Optional project slug.")
def peer_review_main(
    draft_file: str,
    roles: tuple[str, ...],
    model_overrides: tuple[str, ...],
    synthesis: str,
    project_slug: str,
) -> None:
    overrides: dict[str, str] = {}
    for pair in model_overrides:
        if "=" not in pair:
            click.echo(f"--model expects role=alias, got '{pair}'", err=True)
            sys.exit(2)
        key, _, alias = pair.partition("=")
        overrides[key.strip()] = alias.strip()

    draft = Path(draft_file).read_text(encoding="utf-8")
    project = projects_mod.get_project(project_slug) if project_slug else None
    synth = None if synthesis.lower() == "none" else synthesis

    report = peer_review_mod.run_peer_review(
        draft,
        roles=roles,
        model_overrides=overrides,
        synthesis_model=synth,
        project=project,
    )

    for r in report.results:
        click.echo(f"\n## {r.label}  [{r.model}]\n")
        click.echo(r.error or r.text)
    if report.synthesis:
        click.echo(f"\n## Synthesis  [{report.synthesis_model}]\n")
        click.echo(report.synthesis)
    click.echo(f"\nEstimated cost: ${report.total_cost:.4f}")


# ── ra-defense ──────────────────────────────────────────────────────────────


@click.command(help="Generate thesis defense jury questions from a material file.")
@click.argument("material_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--persona", default="strict-reviewer")
@click.option("--model", default="claude")
@click.option("--count", default=8, type=int)
@click.option("--project", "project_slug", default="")
def defense_main(
    material_file: str,
    persona: str,
    model: str,
    count: int,
    project_slug: str,
) -> None:
    material = Path(material_file).read_text(encoding="utf-8")
    project = projects_mod.get_project(project_slug) if project_slug else None
    result = defense_mod.run_defense(
        material,
        persona=persona,
        model=model,
        count=count,
        project=project,
    )
    if result.error:
        click.echo(f"Error: {result.error}", err=True)
        sys.exit(1)
    click.echo(f"## {result.label}  [{result.model}]\n")
    click.echo(result.questions)
    click.echo(f"\nEstimated cost: ${result.cost:.4f}")
