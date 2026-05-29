"""Thesis defense simulator — predict jury questions.

Implements Section 14 of ``research_assistant_development_findings.txt``.
Given an abstract (or chapter), generate the questions a defense committee
is likely to ask, partitioned by examiner persona.
"""
from __future__ import annotations

from dataclasses import dataclass

from research_assistant.common import MODELS, ask_model
from research_assistant.workspace.projects import Project, project_context_block

# ── Personas ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExaminerPersona:
    key: str
    label: str
    system_prompt: str


_PERSONAS: tuple[ExaminerPersona, ...] = (
    ExaminerPersona(
        key="friendly-supervisor",
        label="Friendly supervisor",
        system_prompt=(
            "You are the candidate's supervisor at a thesis defense. You "
            "know the work intimately and ask questions that let the "
            "candidate showcase their strengths, but you still probe "
            "respectfully on weak spots."
        ),
    ),
    ExaminerPersona(
        key="strict-reviewer",
        label="Strict external reviewer",
        system_prompt=(
            "You are an external reviewer on a thesis committee. You have "
            "no relationship with the candidate. You are unfailingly polite "
            "but uncompromising on rigour. You probe overclaims, missing "
            "controls, unstated assumptions, and any gap between the "
            "research question and the evidence."
        ),
    ),
    ExaminerPersona(
        key="methodology-examiner",
        label="Methodology examiner",
        system_prompt=(
            "You are a methodology examiner. You only ask about study "
            "design, controls, confounders, validity threats, "
            "reproducibility, and the relationship between research "
            "question and method."
        ),
    ),
    ExaminerPersona(
        key="statistics-examiner",
        label="Statistics examiner",
        system_prompt=(
            "You are a statistics examiner. You only ask about statistical "
            "tests, assumptions, power, multiple comparisons, effect sizes, "
            "and how the candidate would respond to a non-significant "
            "primary outcome."
        ),
    ),
    ExaminerPersona(
        key="field-expert",
        label="Field expert",
        system_prompt=(
            "You are a senior researcher in the candidate's field. You ask "
            "about how this work positions itself relative to recent "
            "literature, how it differs from the obvious comparable papers, "
            "and what the candidate believes is genuinely novel."
        ),
    ),
)

_QUESTION_TEMPLATE = (
    "{context}\n\n"
    "Generate the questions you would ask the candidate at the defense.\n\n"
    "Cover these categories where applicable:\n"
    "  - novelty\n"
    "  - research question framing\n"
    "  - methodology and controls\n"
    "  - statistics and reproducibility\n"
    "  - limitations\n"
    "  - ethics and data handling\n"
    "  - future work\n\n"
    "Format each question as:\n"
    "  - **Q:** the question, one sentence\n"
    "  - **Probing:** one line on what you are really testing\n"
    "  - **Strong answer cue:** one line on what a confident answer would include\n\n"
    "Aim for {count} questions, ordered hardest-first.\n\n"
    "Material to defend:\n{material}\n"
)


# ── Result types ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DefenseResult:
    persona: str
    label: str
    model: str
    questions: str
    input_tokens: int
    output_tokens: int
    cost: float
    error: str | None = None


# ── Public API ──────────────────────────────────────────────────────────────


def available_personas() -> tuple[ExaminerPersona, ...]:
    return _PERSONAS


def run_defense(
    material: str,
    *,
    persona: str = "strict-reviewer",
    model: str = "claude",
    count: int = 8,
    project: Project | None = None,
    temperature: float = 0.4,
) -> DefenseResult:
    """Generate jury questions from the chosen persona.

    Parameters
    ----------
    material
        The abstract, chapter, or summary the candidate will defend.
    persona
        One of the persona keys returned by :func:`available_personas`.
    model
        Model alias from :mod:`research_assistant.common`.
    count
        Approximate number of questions to ask for.
    project
        Optional project context injected as a preamble.
    temperature
        Slightly higher than default so the question set is varied.
    """
    if not material.strip():
        raise ValueError("Defense material is empty.")
    if model not in MODELS:
        raise ValueError(
            f"Unknown model '{model}'. Available: {', '.join(sorted(MODELS))}"
        )
    examiner = _resolve_persona(persona)
    count = max(3, min(count, 20))

    context = project_context_block(project) if project else ""
    prompt = _QUESTION_TEMPLATE.format(
        context=context, count=count, material=material
    )

    try:
        out = ask_model(
            prompt,
            model=model,
            system=examiner.system_prompt,
            temperature=temperature,
            max_tokens=3000,
        )
    except Exception as exc:
        return DefenseResult(
            persona=examiner.key,
            label=examiner.label,
            model=model,
            questions="",
            input_tokens=0,
            output_tokens=0,
            cost=0.0,
            error=str(exc),
        )
    return DefenseResult(
        persona=examiner.key,
        label=examiner.label,
        model=model,
        questions=out.get("text") or "",
        input_tokens=int(out.get("input_tokens") or 0),
        output_tokens=int(out.get("output_tokens") or 0),
        cost=float(out.get("cost") or 0.0),
    )


# ── Internals ───────────────────────────────────────────────────────────────


def _resolve_persona(key: str) -> ExaminerPersona:
    for persona in _PERSONAS:
        if persona.key == key:
            return persona
    valid = ", ".join(p.key for p in _PERSONAS)
    raise ValueError(f"Unknown persona '{key}'. Available: {valid}")
