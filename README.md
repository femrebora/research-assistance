# research-assistant

[![python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-A3E635)](LICENSE)
[![flask](https://img.shields.io/badge/web%20UI-Flask-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![zotero](https://img.shields.io/badge/Zotero-RAG-CC2936?logo=zotero&logoColor=white)](https://www.zotero.org/)
[![models](https://img.shields.io/badge/models-Claude%20%7C%20Gemini%20%7C%20DeepSeek%20%7C%20GPT--5-7C3AED)](#supported-models)
[![platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-555)](#quick-start)
[![status](https://img.shields.io/badge/status-active-A3E635)](#)

A CLI toolkit + web UI for master's and PhD thesis research. Index your Zotero PDF library, ask research questions with cited answers from your own papers, compare answers across multiple AI models (Claude, Gemini, DeepSeek, GPT/Codex), and save everything for later paraphrasing.

## What's here

### Research

| Script | Purpose |
|--------|---------|
| `researcher.py` | **RAG research assistant** — index Zotero PDFs into local vector store, ask questions with cited answers, compare models |
| `compare.py` | **Multi-model comparison** — ask the same question to multiple AI models simultaneously, with or without document context |
| `ask.py` | **Single-model queries** — ask any question to any configured model (Claude, Gemini, DeepSeek, GPT, local) |
| `zot.py` | **Zotero search** — search your Zotero library from terminal |
| `evidence.py` | **PaperQA2 queries** — query your PDFs via PaperQA2, save cited output |
| `discover.py` | **External paper discovery** — find new papers via OpenAlex, Semantic Scholar, or Elicit |

### Writing pipeline

| Script | Purpose |
|--------|---------|
| `ideas.py` | **Paragraph angles** — get paragraph angles given evidence + a job statement |
| `outline.py` | **Section outline** — hierarchical outline with citation stubs from evidence + a job |
| `critique.py` | **Draft critique** — prose or sentence-anchored diff critique of a paragraph you've written |
| `critic.py` | **Writer + critic** — one model drafts, another critiques (2-model pipeline) |
| `paraphrase.py` | **Writer → paraphraser → checker** — 3-model paraphrase pipeline with meaning verification |
| `coherence.py` | **Multi-paragraph flow** — check chapter-level transitions, redundancy, thesis support |
| `paraphrase_check.py` | **Near-duplicate check** — flag draft paragraphs too similar to your own indexed sources |
| `audit.py` | **Citation audit** — per-source counts, over-cited papers, unused .bib entries, density |
| `verify.py` | **Citation verification** — check all `[@citekey]` placeholders resolve in your `.bib` |
| `claim_verify.py` | **Semantic claim audit** — per-claim, RAG-backed SUPPORTED / PARTIAL / UNSUPPORTED / CONTRADICTED check |
| `pipeline.py` | **Full orchestrator** — retrieve → draft → paraphrase → critique → verify → log |
| `disclose.py` | **AI usage disclosure** — generate venue-ready disclosure from your call logs |

### Web UI

| Script | Purpose |
|--------|---------|
| `app.py` | **Web UI** — Flask web interface for the research assistant |

## Quick Start

### 1. Clone and set up

```bash
git clone https://github.com/femrebora/research-assistant
cd research-assistant
```

### 2. Create Python virtual environment

```bash
python3 -m venv ~/.venvs/thesis
source ~/.venvs/thesis/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp env.example .env
# Edit .env with your API keys and paths
```

Required variables:
```bash
# At least one model provider
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...

# Zotero integration (for researcher.py and zot.py)
ZOTERO_USER_ID=1234567
ZOTERO_API_KEY=...

# Paths
THESIS_ROOT=/home/you/thesis
ZOTERO_STORAGE=/home/you/Zotero/storage
```

### 4. Index your papers

```bash
# Index all Zotero PDFs (one-time, takes a few minutes)
./researcher.py index

# Or index a specific collection
./researcher.py index --collection "Chapter 1" --limit 20
```

### 5. Ask your first question

```bash
./researcher.py ask "What are the main approaches to filtering NUMT in clinical mtDNA?"
```

## CLI Usage

### Researcher — RAG over your papers

```bash
# Index management
./researcher.py index                          # Index all Zotero PDFs
./researcher.py index --collection "Ch. 1"     # Index a specific collection
./researcher.py index --force                   # Re-index everything
./researcher.py index --limit 50               # Index first 50 items only
./researcher.py stats                          # View index statistics

# Ask questions with cited, paraphrase-ready answers
./researcher.py ask "What is NUMT contamination?"
./researcher.py ask "..." --model gemini        # Use a different model
./researcher.py ask "..." --k 10               # Retrieve fewer chunks
./researcher.py ask "..." --threshold 0.4      # Stricter relevance filter
./researcher.py ask "..." --save session_name  # Save Q&A to a session file
./researcher.py ask "..." --raw                # Plain text output (for piping)

# Compare answers from multiple models (same RAG context)
./researcher.py ask "..." --compare claude,gemini,gpt
./researcher.py ask "..." --compare claude,deepseek --save comparison

# Browse past sessions
./researcher.py sessions                        # List all sessions
./researcher.py sessions --view session_name    # View a session
./researcher.py sessions --view last            # View most recent session
```

### Compare — Multi-model comparison

```bash
# Direct comparison (no document context)
./compare.py "What is NUMT?" --models claude,gemini,gpt
./compare.py "..." --models claude,sonnet,haiku,gemini,deepseek,gpt

# RAG comparison (same context from your indexed papers)
./compare.py "What approaches exist for NUMT filtering?" --models claude,gemini --rag
./compare.py "..." --models claude,gpt --rag --k 15 --threshold 0.4

# Save comparison to session
./compare.py "..." --models claude,gemini,gpt --save my_comparison
```

### Other tools

```bash
# Ask a single model (quick questions)
./ask.py "Explain MitoScape's filtering approach" --model claude
./ask.py "Same question" --model gemini           # Second opinion
./ask.py "Same question" --model deepseek          # Cheaper option

# Search Zotero library
./zot.py "NUMT contamination"
./zot.py "MitoScape" --limit 20 --bib             # Just citekeys

# Evidence query via PaperQA2
./evidence.py "What evidence exists for NUMT affecting variant calling?" --save evidence/ch1.md

# Discover new papers from OpenAlex / Semantic Scholar / Elicit
./discover.py "NUMT filtering clinical mtDNA" --source openalex --limit 15
./discover.py "..." --source semantic_scholar --year-from 2020
./discover.py "..." --export bibtex > new_papers.bib
```

### Writing pipeline

```bash
# 1. Get paragraph angles from evidence
./ideas.py evidence/ch1/numt.md --job "Establish NUMT as clinically significant"

# 2. Or generate a full hierarchical outline (one stub per paragraph)
./outline.py evidence/ch1/numt.md \
    --job "Argue NUMT filtering is mandatory in clinical mtDNA pipelines" \
    --sections 4 --depth 2 --save outlines/ch1.md

# 3. Critique your draft paragraph (prose mode or sentence-anchored)
./critique.py drafts/para.md --job "Define NUMT contamination"
./critique.py drafts/para.md --job "..." --diff           # S1, S2, ... annotations

# 4. Check whole-chapter coherence and thesis support
./coherence.py drafts/chapter1.md \
    --thesis "NUMT filtering is mandatory for clinical mtDNA pipelines"

# 5. Catch paragraphs that drifted too close to source wording
./paraphrase_check.py drafts/chapter1.md --threshold 0.85

# 6. Audit citation usage (density, over-cites, unused .bib entries)
./audit.py drafts/chapter1.md --bib bib/thesis.bib --over-cite 6

# 7. Verify citations resolve to the .bib (catches typos / hallucinations)
./verify.py drafts/chapter1.md --bib bib/thesis.bib
```

### Multi-model writing pipeline

Five composable tools chain LLMs into a write → paraphrase → critique → verify → disclose flow. Each works standalone or as part of `pipeline.py`.

- [paraphrase.py](#paraphrasepy--writer--paraphraser--checker) — writer → paraphraser → checker (3 models)
- [critic.py](#criticpy--writer--critic) — writer + critic (2 models)
- [claim_verify.py](#claim_verifypy--semantic-claim-audit) — semantic per-claim support audit
- [pipeline.py](#pipelinepy--full-orchestrator) — full 6-step orchestrator
- [disclose.py](#disclosepy--ai-usage-disclosure) — generate a venue-ready AI-usage statement

#### paraphrase.py — Writer → Paraphraser → Checker

Three models in series:

1. **Writer** drafts the paragraph from your brief + optional sources.
2. **Paraphraser** rewrites the draft in fresh academic prose (same claims, different wording, citations preserved).
3. **Checker** compares meaning between draft and paraphrase and flags drift, lost citations, or new citations.

Each stage is logged to `~/thesis/logs/YYYY-MM-DD.jsonl` automatically, so the entire chain is auditable for AI-usage disclosure.

```bash
# The exact form from my_request:
./paraphrase.py "Define NUMT contamination" \
    --writer claude \
    --paraphraser gemini \
    --checker gpt \
    --sources evidence/ch1.md \
    --save outputs/numt_para.md

# Skip the writer stage and paraphrase a draft you already wrote:
./paraphrase.py drafts/para.md --skip-writer \
    --paraphraser claude --checker gpt
```

| Flag | Required | Default | What it does |
|---|---|---|---|
| `BRIEF_OR_DRAFT` (positional) | yes | — | A one-line brief (writer mode) or a path to an existing draft (`--skip-writer`). |
| `--writer` / `-w` | yes (unless `--skip-writer`) | — | Model that drafts the paragraph. |
| `--paraphraser` / `-p` | yes | — | Model that rewrites the draft. |
| `--checker` / `-c` | yes | — | Model that audits meaning. |
| `--sources` / `-s` | no | — | One or more source files. Repeatable (`-s a.md -s b.md`). |
| `--skip-writer` | no | off | Treat the positional arg as an existing draft and skip stage 1. |
| `--temperature` / `-t` | no | 0.3 | Writer + paraphraser temperature. Checker is fixed at 0.1 (low). |
| `--interactive` / `-i` | no | off | Pause between stages; see below. |
| `--save` / `-o` | no | — | Save the full chain (brief, draft, paraphrase, check) as one markdown file. |
| `--raw` | no | off | Plain text output (for piping). |

##### Interactive (`--interactive`) — edit between stages

With `-i`, the script stops after every stage and asks what to do:

```
→ writer: claude (anthropic/claude-opus-4-7)
╭──────────────── writer — anthropic/claude-opus-4-7 ────────────────╮
│ NUMT contamination refers to nuclear copies of mitochondrial DNA   │
│ that confound variant-calling pipelines [@smith2024]. ...          │
╰────────────────────────────────────────────────────────────────────╯
[writer] [a]ccept / [e]dit / [r]egenerate / [q]uit [a]: e
  (opens $EDITOR with the draft pre-loaded; save & quit to continue)
✓ writer edited (412 chars accepted)

→ paraphraser: gemini (gemini/gemini-2.5-pro)
...
```

- **`a` accept** — keep the model output as-is; the next stage consumes it.
- **`e` edit** — open `$EDITOR` (falls back to `$VISUAL`, then `nano`) on a temp file pre-loaded with the stage output. Whatever you save replaces the output and feeds the next stage. Empty edits are rejected (keeps the original).
- **`r` regenerate** — re-run the same stage with the same prompt (useful when you want a different sampling).
- **`q` quit** — abort. Anything already written via `--save` stays on disk; in-memory state is dropped.

Tip: combine `--interactive` with mixed API/CLI models. You can let `claude` draft via the Anthropic API, edit the draft yourself, paraphrase via `gemini-cli` (your Gemini CLI subscription), and check with local `ollama-cli` — all in one run.

#### critic.py — Writer + Critic

Two-model pipeline: one model drafts a paragraph, a **different** model critiques it. Useful for stress-testing prompts or getting an adversarial second read of an AI-generated paragraph. (Distinct from `critique.py`, which critiques text *you* wrote.)

```bash
./critic.py "Define NUMT contamination" \
    --writer claude \
    --critic gpt \
    --sources evidence/ch1.md \
    --save outputs/critic_run.md
```

| Flag | Required | Default | What it does |
|---|---|---|---|
| `JOB` (positional) | yes | — | One sentence describing what the paragraph must do. |
| `--writer` / `-w` | yes | — | Model that drafts the paragraph. |
| `--critic` / `-c` | yes | — | Model that critiques the draft. |
| `--sources` / `-s` | no | — | Source files for the writer to cite. Repeatable. |
| `--writer-temp` | no | 0.3 | Writer temperature. |
| `--critic-temp` | no | 0.2 | Critic temperature. |
| `--save` / `-o` | no | — | Save the full chain (job, draft, critique) as markdown. |
| `--raw` | no | off | Plain text output. |

The critic ends its review with one line: **`VERDICT: ACCEPT | REVISE | REJECT`**.

#### claim_verify.py — Semantic claim audit

Where `verify.py` only checks that `[@citekey]` placeholders exist in your `.bib`, this script does the harder job: for every factual claim in your draft, it retrieves the most relevant chunks from your Zotero RAG index and asks an LLM to classify support.

Labels: **SUPPORTED · PARTIAL · UNSUPPORTED · CONTRADICTED**.

```bash
./claim_verify.py drafts/chapter1.md
./claim_verify.py drafts/chapter1.md --k 6 --model sonnet --threshold 0.30
./claim_verify.py drafts/chapter1.md --json > claim_audit.json
./claim_verify.py drafts/chapter1.md --limit 10  # dry-run on first 10 claims
```

| Flag | Default | What it does |
|---|---|---|
| `--model` / `-m` | `sonnet` | LLM that adjudicates support. |
| `--k` / `-k` | 6 | Chunks to retrieve per claim. |
| `--threshold` / `-t` | 0.30 | Cosine similarity threshold for retrieval. |
| `--min-chars` | 40 | Skip sentences shorter than this. |
| `--limit` | none | Audit only the first N claims. |
| `--json` | off | Machine-readable JSON output. |

**Exit code is non-zero** if any claim is `UNSUPPORTED` or `CONTRADICTED`, so the script is usable as a pre-submission / CI gate.

Heuristic for claim detection: sentences containing a `[@citekey]` or factual signal words (*shows, demonstrates, reports, found, established, significantly, associated with, …*) are treated as claims. Plain narrative sentences are skipped.

#### pipeline.py — Full orchestrator

The 6-step chain from `my_request`, in one command:

1. Retrieve context from the Zotero RAG index.
2. Writer drafts a paragraph from the retrieved sources.
3. Paraphraser rewrites it in fresh prose.
4. Critic critiques the paraphrased paragraph.
5. Citation verifier checks `[@citekeys]` against your `.bib`.
6. AI-usage log entry (automatic; every model call is recorded).

```bash
./pipeline.py "What is NUMT contamination?" \
    --writer claude \
    --paraphraser gemini \
    --critic gpt \
    --save outputs/numt_run.md

# Skip the citation verifier (e.g. you haven't built the .bib yet):
./pipeline.py "..." --writer claude --paraphraser gemini --critic gpt --no-verify
```

| Flag | Default | What it does |
|---|---|---|
| `QUESTION` (positional) | — | The question/job the paragraph must answer. |
| `--writer` / `-w` | — (required) | Drafts the paragraph from retrieved sources. |
| `--paraphraser` / `-p` | — (required) | Rewrites the draft. |
| `--critic` / `-c` | — (required) | Critiques the paraphrased paragraph. |
| `--k` / `-k` | 12 | RAG chunks to retrieve. |
| `--threshold` / `-t` | 0.30 | Similarity threshold. |
| `--bib` | `bib/thesis.bib` | Bibliography for the verifier step. |
| `--no-verify` | off | Skip the citation-verifier step. |
| `--save` / `-o` | — | Save the full report (retrieval + each stage + verifier + cost table). |
| `--raw` | off | Plain text output. |

The verifier embedded in this pipeline is the lightweight citekey check from `verify.py`. For deeper, RAG-backed claim-support verification, run `claim_verify.py` against the saved paraphrase afterward.

#### disclose.py — AI usage disclosure

Aggregates `~/thesis/logs/*.jsonl` into a publication-ready disclosure of which models were used, how often, and at what cost.

```bash
./disclose.py                                          # generic template, console preview
./disclose.py --venue elsevier --save logs/disclosure.md
./disclose.py --venue thesis --since 2026-01-01 --until 2026-05-22
./disclose.py --json --save logs/disclosure.json       # machine-readable
./disclose.py --log-dir /path/to/other/logs            # override log location
```

| Flag | Default | What it does |
|---|---|---|
| `--venue` | `generic` | One of `generic`, `elsevier`, `springer`, `acm`, `thesis` — picks the preamble wording. |
| `--since` | none | ISO date (YYYY-MM-DD) lower bound. |
| `--until` | none | ISO date (YYYY-MM-DD) upper bound. |
| `--json` | off | Machine-readable JSON output. |
| `--save` / `-o` | — | Save the rendered disclosure to a file. |
| `--log-dir` | `~/thesis/logs` | Override the log directory. |

The output table shows API and CLI calls in separate rows: API calls report tokens and estimated $-cost; CLI calls report tokens as `—` and cost as `subscription` (since CLI billing happens at the subscription layer).

### Model routing: API vs CLI

Every tool that takes a model alias supports two routing modes:

| Route | Aliases | Where billing happens | Notes |
|---|---|---|---|
| **API** | `claude`, `sonnet`, `haiku`, `gemini`, `flash`, `deepseek`, `gpt`, `gpt-mini`, `codex`, `local` | Per-token, against the provider's API key in `.env` (or free for `local` via LiteLLM-managed Ollama). | Default. Full token + cost reporting. |
| **CLI** | `claude-cli`, `gemini-cli`, `codex-cli`, `ollama-cli` | The respective CLI binary on your machine — your Claude Code / Gemini CLI / Codex subscription, or free for local Ollama. | Tokens are not counted (the CLIs do not surface them). Cost is recorded as $0. |

You can mix freely on a per-stage basis:

```bash
# Draft via API, paraphrase via CLI subscription, check on local Ollama.
./paraphrase.py "Define NUMT contamination" \
    --writer claude \
    --paraphraser gemini-cli \
    --checker ollama-cli \
    --sources evidence/ch1.md \
    --interactive

# Three CLI subscriptions side-by-side:
./compare.py "What is NUMT?" --models claude-cli,gemini-cli,codex-cli

# Single-shot via any local binary:
./ask.py "Explain MitoScape's filtering approach" --model claude-cli
./ask.py "Same question" --model ollama-cli
```

#### CLI alias reference

| Alias | Default command | Override env var |
|---|---|---|
| `claude-cli` | `claude -p "<prompt>"` | `CLAUDE_CLI_CMD` |
| `gemini-cli` | `gemini -p "<prompt>"` | `GEMINI_CLI_CMD` |
| `codex-cli` | `codex exec "<prompt>"` | `CODEX_CLI_CMD` |
| `ollama-cli` | `ollama run llama3.3 "<prompt>"` | `OLLAMA_CLI_CMD` |

The prompt is appended as the **final positional argument** (no shell, so quoting is safe). To change the binary, flags, or local Ollama model, set the corresponding env var in `.env`. Example:

```bash
# In .env
CLAUDE_CLI_CMD="claude -p --output-format text"
GEMINI_CLI_CMD="gemini --model gemini-2.5-flash -p"
OLLAMA_CLI_CMD="ollama run qwen2.5"
CLI_TIMEOUT=900     # seconds; default 600
EDITOR=nvim         # used by ./paraphrase.py --interactive
```

#### CLI prerequisites

Before you can use a `*-cli` alias:

1. **Install the CLI binary** and confirm it's on `$PATH` (`which claude` / `which gemini` / `which codex` / `which ollama`).
2. **Authenticate it once.** Run the binary's own login flow (e.g. `claude login`, `gemini auth`, `codex auth`, or just leave Ollama running locally). The router only invokes the binary — it doesn't manage auth.
3. **Test it with one call** before threading it into the pipeline:
   ```bash
   ./ask.py "Say hello in five words" --model gemini-cli
   ```
   If the binary isn't found, you'll get a clean error pointing at the `*_CLI_CMD` env var to override.

## Web UI

Launch the Flask web interface:

```bash
flask --app app run
# Or with a custom port and debug mode:
flask --app app run --port 5050 --debug
```

Open **http://localhost:5000** in your browser.

### Pages

- **Dashboard** — index stats, quick-ask box, recent sessions
- **Ask a Question** — type a question, select a model, get cited answers with source cards
- **Compare Models** — ask multiple models simultaneously, see side-by-side comparison
- **Sessions** — browse, view, and delete saved Q&A sessions
- **Manage Index** — start background indexing with progress tracking

## Supported Models

| Alias | Model | Provider | Input $/1M | Output $/1M |
|-------|-------|----------|-----------|------------|
| `claude` | Claude Opus 4.7 | Anthropic | $15.00 | $75.00 |
| `sonnet` | Claude Sonnet 4.6 | Anthropic | $3.00 | $15.00 |
| `haiku` | Claude Haiku 4.5 | Anthropic | $0.80 | $4.00 |
| `gemini` | Gemini 2.5 Pro | Google | $1.25 | $5.00 |
| `flash` | Gemini 2.5 Flash | Google | $0.075 | $0.30 |
| `deepseek` | DeepSeek Chat | DeepSeek | $0.27 | $1.10 |
| `gpt` | GPT-5 | OpenAI | $1.25 | $10.00 |
| `gpt-mini` | GPT-5 Mini | OpenAI | $0.15 | $0.60 |
| `codex` | GPT-5 (alias) | OpenAI | $1.25 | $10.00 |
| `local` | Ollama (configurable) | Local | $0.00 | $0.00 |
| `claude-cli` | Claude Code CLI subscription | Local binary | (subscription) | (subscription) |
| `gemini-cli` | Gemini CLI subscription | Local binary | (subscription) | (subscription) |
| `codex-cli` | Codex CLI subscription | Local binary | (subscription) | (subscription) |
| `ollama-cli` | Local `ollama run` | Local binary | $0.00 | $0.00 |

Edit the `MODELS` dict (or `CLI_PROVIDERS` for CLI aliases) in `common.py` to change model versions or add new providers. The `local` alias defaults to `ollama/llama3.3`; override with `OLLAMA_MODEL` in your `.env` (e.g. `OLLAMA_MODEL=ollama/qwen2.5`). For CLI aliases, override the exact command with `CLAUDE_CLI_CMD` / `GEMINI_CLI_CMD` / `CODEX_CLI_CMD` / `OLLAMA_CLI_CMD`.

## Typical Thesis Workflow

```bash
# 1. Index your Zotero library (once)
./researcher.py index

# 2. (Optional) Discover papers you don't have yet
./discover.py "NUMT contamination clinical mtDNA" --year-from 2020 --export bibtex >> new.bib

# 3. Research a topic — ask questions, save sessions
./researcher.py ask "What are the clinical implications of NUMT contamination?" --save numt_clinical
./researcher.py ask "What tools exist for NUMT detection?" --session numt_clinical
./researcher.py ask "What are the limitations of current approaches?" --session numt_clinical

# 4. Compare model perspectives on tricky questions
./compare.py "Is NUMT filtering necessary for clinical mtDNA sequencing?" --models claude,gemini,gpt --rag

# 5. Get evidence for a specific paragraph
./evidence.py "NUMT filtering methods comparison" --save evidence/ch1/numt_methods.md

# 6. Plan: paragraph angles + (optional) full outline
./ideas.py evidence/ch1/numt_methods.md --job "Compare NUMT detection tools"
./outline.py evidence/ch1/numt_methods.md --job "Compare NUMT detection tools" --sections 3

# 7. Write your paragraph yourself (in your editor / Google Docs)

# 8. Critique your draft — paragraph by paragraph
./critique.py drafts/ch1_para_3.md --job "Compare NUMT detection tools"
./critique.py drafts/ch1_para_3.md --job "..." --diff       # sentence-anchored

# 9. When the chapter is assembled, run the pre-submission gauntlet
./coherence.py drafts/chapter1.md --thesis "NUMT filtering is mandatory in clinical mtDNA"
./paraphrase_check.py drafts/chapter1.md --threshold 0.85
./audit.py drafts/chapter1.md --bib bib/thesis.bib
./verify.py drafts/chapter1.md --bib bib/thesis.bib
./claim_verify.py drafts/chapter1.md --k 6 --model sonnet     # semantic per-claim audit

# 10. (Optional) End-to-end: retrieve → draft → paraphrase → critique → verify, interactively.
./pipeline.py "What is NUMT contamination?" \
    --writer claude --paraphraser gemini-cli --critic gpt \
    --save outputs/numt_run.md
# Or run the 3-model paraphrase step on its own with mid-flight editing:
./paraphrase.py "Define NUMT contamination" \
    --writer claude --paraphraser gemini --checker gpt \
    --sources evidence/ch1.md --interactive --save outputs/numt_para.md

# 11. Generate the AI-usage disclosure for submission.
./disclose.py --venue thesis --save thesis/appendix_disclosure.md
```

## Architecture

```
Index:  Zotero API → ZOTERO_STORAGE PDFs → pdfplumber → text
        → chunk (800 char, 200 overlap, sentence-boundary aware)
        → litellm embedding (text-embedding-3-small, 1536 dims)
        → ChromaDB (cosine similarity, persistent on disk)

Query:  question → embed → ChromaDB top-k → deduplicate (max 3 chunks/source)
        → context + system prompt → common.ask_model()
        → bulleted answer with [@citekey] citations

Compare:  same RAG context → parallel ThreadPoolExecutor calls
          → side-by-side Rich table (CLI) or card grid (web UI)
```

Every model call is logged to `~/thesis/logs/YYYY-MM-DD.jsonl` with timestamp, model, prompt, response, and cost — ready for AI-usage disclosure.

## Logging & AI Disclosure

All model calls (every script, every model, both API and CLI routes) append one JSON line to `~/thesis/logs/YYYY-MM-DD.jsonl`:

```jsonc
// API call — full token counts available
{"timestamp": "2026-05-19T14:30:00+00:00", "model_alias": "claude",
 "model_full": "anthropic/claude-opus-4-7", "via": "api",
 "prompt": "...", "response": "...",
 "input_tokens": 1200, "output_tokens": 400}

// CLI call — tokens unavailable (the CLI doesn't surface them); via marks the route
{"timestamp": "2026-05-19T14:32:00+00:00", "model_alias": "gemini-cli",
 "model_full": "gemini -p", "via": "cli",
 "prompt": "...", "response": "...",
 "input_tokens": null, "output_tokens": null}
```

For venues requiring AI-usage disclosure, run [`./disclose.py`](#disclosepy--ai-usage-disclosure) (templates for `generic`, `elsevier`, `springer`, `acm`, and `thesis`) or use the `/ars-disclosure` command if the academic-research-skills plugin is installed. API and CLI calls are reported separately in both the table and the totals line.

## FAQ

**Q: Do I need all model provider API keys?**
No. Only set the keys for providers you plan to use. At minimum, have one key.

**Q: How long does indexing take?**
~5-10 seconds per paper (text extraction + embedding). 100 papers ≈ 10 minutes.

**Q: Can I index without Zotero?**
Currently, no. The indexer uses the Zotero API for metadata (authors, citekeys, DOIs). PDF-only indexing could be added.

**Q: What if a PDF has no extractable text?**
Scanned/image-only PDFs are skipped with a warning. Use OCR first.

**Q: Can I use a local embedding model?**
Yes. Change `DEFAULT_EMBED_MODEL` in `researcher.py` to `"ollama/nomic-embed-text"` or any LiteLLM-supported embedding model.

**Q: How do I update the index after adding new papers to Zotero?**
Run `./researcher.py index` again. Already-indexed papers are skipped (checked by Zotero item key). Use `--force` to re-index everything.

**Q: When should I use a `*-cli` alias vs. the API alias?**
Use `claude-cli` / `gemini-cli` / `codex-cli` when you already pay for the corresponding CLI subscription and want those calls to flow through it instead of a per-token API bill. Use the API aliases (`claude`, `gemini`, `gpt`) when you want exact token + cost reporting in `./disclose.py`, when you're scripting unattended runs (CLIs sometimes prompt for re-auth), or when the API model version differs from the CLI's pinned version. You can mix freely: `--writer claude --paraphraser gemini-cli --checker codex-cli` is fine.

**Q: What if my CLI binary isn't on `$PATH` or uses different flags?**
Override the full command with the matching env var in `.env`:
```bash
CLAUDE_CLI_CMD="/opt/anthropic/claude -p --output-format text"
GEMINI_CLI_CMD="gemini --model gemini-2.5-flash -p"
```
The prompt is appended as the final positional argument, so anything you put in the env var is treated as the leading command + flags.

**Q: `--interactive` opened the wrong editor (or nano when I wanted nvim). How do I change it?**
Set `EDITOR` (or `VISUAL`) in `.env` or your shell. `paraphrase.py --interactive` checks `$EDITOR`, then `$VISUAL`, then falls back to `nano`. Empty saves are treated as "keep the model output" — there's no way to accidentally pass an empty paragraph to the next stage.

**Q: My interactive run died on stage 2. Did I lose stage 1?**
If you passed `--save outputs/run.md`, the file is written only after all three stages finish, so a crash mid-run drops the partial work. Either re-run (regenerate is cheap), or — for paragraph-by-paragraph control — copy the writer output out of the terminal between stages.

**Q: Are CLI calls counted in my AI-usage disclosure?**
Yes. Every CLI call appends a log line with `"via": "cli"` and is shown as a separate row in `./disclose.py` (route column = `cli`). Token counts and dollar cost are blank for CLI calls because the CLIs don't surface tokens; the disclosure makes the subscription nature explicit ("n/a (CLI subscription)").

**Q: Can I run the full pipeline non-interactively for batch use?**
Yes. Don't pass `--interactive` and the pipeline runs end-to-end without prompts. For unattended jobs, prefer API aliases (CLIs may stall waiting for re-auth) and use `--save` so the output file is the single source of truth.
