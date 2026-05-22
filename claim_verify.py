#!/usr/bin/env python3
"""claim_verify.py — semantic claim-by-claim source-support verification.

Splits a draft into claim-bearing sentences, retrieves the most relevant
chunks from your Zotero RAG index for each claim, and asks an LLM to
classify support: SUPPORTED / PARTIAL / UNSUPPORTED / CONTRADICTED.

Use this in addition to verify.py (which only checks that [@citekeys]
resolve to your .bib). This script catches the harder problem:
a citation exists, but does the cited paper actually back the claim?

Usage:
    ./claim_verify.py drafts/ch1_full.md
    ./claim_verify.py drafts/ch1_full.md --k 6 --model sonnet --threshold 0.30
    ./claim_verify.py drafts/ch1_full.md --json > report.json
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from common import MODELS, ask_model, read_file

console = Console()

CLAIM_PROMPT = """You are auditing whether a single thesis claim is supported by retrieved sources.

## Claim (one sentence from the thesis)
{claim}

## Retrieved source excerpts (from the author's own Zotero library)
{context}

## Your task
Classify support for the claim with ONE of these labels:

- SUPPORTED — at least one source clearly states the claim or a stronger form.
- PARTIAL — sources support part of the claim but not all of it, or support a weaker version.
- UNSUPPORTED — no retrieved source backs the claim.
- CONTRADICTED — at least one retrieved source disagrees with the claim.

Output in EXACTLY this format (no extra prose):

LABEL: <one of the four labels>
EVIDENCE: <one short quote OR "none">
CITEKEY: <@citekey of the best supporting source, OR "none">
NOTE: <one sentence on why; "none" if SUPPORTED with a clear quote>
"""


# Heuristic claim detector: sentences containing a citation are candidate claims;
# sentences with strong factual signals also qualify.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[])")
_CITE_IN_TEXT = re.compile(r"\[@[a-zA-Z][a-zA-Z0-9_:-]*")
_FACTUAL_SIGNALS = re.compile(
    r"\b(shows?|demonstrates?|reports?|found|reveal(?:ed)?|indicates?|"
    r"established?|confirm(?:ed)?|prove[ds]?|argue[ds]?|claim(?:ed)?|"
    r"significantly|increase[ds]?|decrease[ds]?|associated with)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ClaimReport:
    sentence: str
    label: str
    evidence: str
    citekey: str
    note: str
    has_citation: bool


def extract_claims(draft: str, min_chars: int = 40) -> list[str]:
    """Pick out sentences that look like factual claims (cited or factual-signal-bearing)."""
    text = re.sub(r"\s+", " ", draft).strip()
    sentences = _SENTENCE_SPLIT.split(text)
    claims = []
    for raw in sentences:
        s = raw.strip()
        if len(s) < min_chars:
            continue
        if _CITE_IN_TEXT.search(s) or _FACTUAL_SIGNALS.search(s):
            claims.append(s)
    return claims


def _parse_label_block(text: str) -> dict[str, str]:
    out = {"LABEL": "UNSUPPORTED", "EVIDENCE": "none", "CITEKEY": "none", "NOTE": "none"}
    for line in text.splitlines():
        line = line.strip()
        for k in out:
            prefix = f"{k}:"
            if line.upper().startswith(prefix):
                out[k] = line[len(prefix):].strip()
                break
    return out


def verify_claim(
    claim: str,
    retrieve_fn,
    model: str,
    k: int,
    threshold: float,
) -> ClaimReport:
    """Verify a single claim. retrieve_fn(query, k, threshold) -> list[dict] of RAG chunks."""
    from researcher import build_context, deduplicate_by_source  # local import — heavy deps

    results = retrieve_fn(claim, k, threshold)
    deduped = deduplicate_by_source(results) if results else []
    context = build_context(deduped) if deduped else "(no relevant excerpts retrieved)"

    prompt = CLAIM_PROMPT.format(claim=claim, context=context)
    resp = ask_model(prompt, model=model, temperature=0.1)
    parsed = _parse_label_block(resp["text"])

    return ClaimReport(
        sentence=claim,
        label=parsed["LABEL"].upper(),
        evidence=parsed["EVIDENCE"],
        citekey=parsed["CITEKEY"],
        note=parsed["NOTE"],
        has_citation=bool(_CITE_IN_TEXT.search(claim)),
    )


def _render(reports: list[ClaimReport]) -> None:
    counts = {"SUPPORTED": 0, "PARTIAL": 0, "UNSUPPORTED": 0, "CONTRADICTED": 0}
    for r in reports:
        counts[r.label] = counts.get(r.label, 0) + 1

    summary = Table(title="Claim verification summary", show_header=False)
    summary.add_column(style="cyan")
    summary.add_column(style="green")
    summary.add_row("Claims audited", str(len(reports)))
    for label, n in counts.items():
        summary.add_row(label, str(n))
    console.print(summary)

    table = Table(title="Per-claim results", show_lines=True)
    table.add_column("#", style="dim", no_wrap=True)
    table.add_column("Label", style="bold", no_wrap=True)
    table.add_column("Claim", style="white", width=50)
    table.add_column("Best citekey", style="cyan", no_wrap=True)
    table.add_column("Note", style="dim", width=30)

    colors = {
        "SUPPORTED": "green",
        "PARTIAL": "yellow",
        "UNSUPPORTED": "red",
        "CONTRADICTED": "red",
    }
    for i, r in enumerate(reports, 1):
        color = colors.get(r.label, "white")
        claim_trunc = r.sentence if len(r.sentence) < 120 else r.sentence[:117] + "..."
        table.add_row(
            str(i),
            f"[{color}]{r.label}[/{color}]",
            claim_trunc,
            r.citekey,
            r.note if len(r.note) < 80 else r.note[:77] + "...",
        )
    console.print(table)


@click.command()
@click.argument("draft_file")
@click.option("--model", "-m", default="sonnet",
              type=click.Choice(list(MODELS.keys())),
              help="LLM that adjudicates support.")
@click.option("--k", "-k", default=6, type=int,
              help="Chunks to retrieve per claim.")
@click.option("--threshold", "-t", default=0.30, type=float,
              help="Cosine similarity threshold for retrieval.")
@click.option("--min-chars", default=40, type=int,
              help="Skip sentences shorter than this.")
@click.option("--limit", default=None, type=int,
              help="Audit at most this many claims (None = all).")
@click.option("--json", "as_json", is_flag=True, help="Output JSON instead of tables.")
def main(draft_file, model, k, threshold, min_chars, limit, as_json):
    """Verify each factual claim in a draft against retrieved Zotero sources."""
    try:
        from researcher import _get_collection, retrieve_chunks
    except ImportError:
        console.print("[red]Cannot import researcher.py. Make sure it's in the same directory.[/red]")
        sys.exit(1)

    draft = read_file(draft_file)
    claims = extract_claims(draft, min_chars=min_chars)
    if limit is not None:
        claims = claims[:limit]

    if not claims:
        console.print("[yellow]No factual claims detected in draft.[/yellow]")
        sys.exit(0)

    console.print(f"[dim]→ {len(claims)} claims to audit using {model} (k={k}, threshold={threshold})[/dim]\n")

    collection = _get_collection()

    def _retrieve(query: str, k_local: int, threshold_local: float):
        return retrieve_chunks(query, collection=collection, k=k_local, threshold=threshold_local)

    reports: list[ClaimReport] = []
    for i, claim in enumerate(claims, 1):
        console.print(f"[dim]  [{i}/{len(claims)}] {claim[:80]}{'...' if len(claim) > 80 else ''}[/dim]")
        try:
            reports.append(verify_claim(claim, _retrieve, model=model, k=k, threshold=threshold))
        except Exception as e:
            reports.append(
                ClaimReport(
                    sentence=claim,
                    label="UNSUPPORTED",
                    evidence="none",
                    citekey="none",
                    note=f"verification error: {e}",
                    has_citation=bool(_CITE_IN_TEXT.search(claim)),
                )
            )

    if as_json:
        click.echo(json.dumps([asdict(r) for r in reports], indent=2, ensure_ascii=False))
    else:
        _render(reports)

    failed = sum(1 for r in reports if r.label in ("UNSUPPORTED", "CONTRADICTED"))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
