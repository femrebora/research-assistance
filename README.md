# research-assistant

[![python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-A3E635)](LICENSE)
[![flask](https://img.shields.io/badge/web%20UI-Flask-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![models](https://img.shields.io/badge/models-Claude%20%7C%20Gemini%20%7C%20DeepSeek%20%7C%20GPT--5-7C3AED)](#supported-models)

A research toolkit for master's and PhD thesis work. Index your Zotero library, ask questions against your papers, compare model answers, and run the full draft → paraphrase → verify pipeline — all from a web UI.

## Quick start

```bash
git clone https://github.com/femrebora/research-assistant
cd research-assistant
./setup.sh
source ~/.venvs/thesis/bin/activate
cp env.example .env    # then edit .env with your API keys
ra-web                 # open http://127.0.0.1:5050
```

That's it. Everything else — asking questions, comparing models, running tools, managing the index — happens in the browser.

## Configuration

Put your keys in `.env`. At minimum, set one model provider:

```bash
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...
```

For Zotero integration, also set:

```bash
ZOTERO_USER_ID=1234567
ZOTERO_API_KEY=...
THESIS_ROOT=/home/you/thesis          # default: ~/thesis
ZOTERO_STORAGE=/home/you/Zotero/storage
```

All model calls are logged to `~/thesis/logs/` for disclosure purposes. Use the built-in disclosure tool in the web UI to generate a venue-ready statement.

## Web UI

The dashboard at `http://127.0.0.1:5050` gives you:

- **Dashboard** — index stats, quick-ask, recent sessions
- **Ask** — RAG-backed Q&A against your indexed papers, with citations
- **Compare** — side-by-side answers from multiple models
- **Sessions** — browse, view, and delete saved Q&A
- **Index** — background indexing with progress tracking
- **Tools** — every CLI tool below is also available as a form at `/tools/<name>`

## CLI (optional)

Everything in the web UI is also available from the terminal:

| Command | What it does |
|---|---|
| `ra-researcher ask` | RAG question with cited answer |
| `ra-researcher index` | Index Zotero PDFs |
| `ra-compare` | Multi-model comparison |
| `ra-ask` | Single-model question |
| `ra-zot` | Search your Zotero library |
| `ra-discover` | Find papers via OpenAlex / Semantic Scholar |
| `ra-evidence` | PaperQA2 cited query |
| `ra-ideas` | Paragraph angles from evidence |
| `ra-outline` | Section outline with citation stubs |
| `ra-critique` | Draft critique |
| `ra-critic` | Writer + critic pipeline |
| `ra-paraphrase` | Writer → paraphraser → checker pipeline |
| `ra-coherence` | Chapter coherence analysis |
| `ra-audit` | Citation audit |
| `ra-verify` | Citekey resolution against .bib |
| `ra-claim-verify` | Semantic per-claim support audit |
| `ra-originality` | Originality check (internal + OpenAlex / Crossref) |
| `ra-disclose` | AI-usage disclosure statement |
| `ra-pipeline` | Full end-to-end orchestrator |

Run any command with `--help` for options.

## Supported models

| Alias | Model | Input $/1M | Output $/1M |
|---|---|---|---|
| `claude` | Claude Opus 4.7 | $15.00 | $75.00 |
| `sonnet` | Claude Sonnet 4.6 | $3.00 | $15.00 |
| `haiku` | Claude Haiku 4.5 | $0.80 | $4.00 |
| `gemini` | Gemini 2.5 Pro | $1.25 | $5.00 |
| `flash` | Gemini 2.5 Flash | $0.075 | $0.30 |
| `deepseek` | DeepSeek Chat | $0.27 | $1.10 |
| `gpt` | GPT-5 | $1.25 | $10.00 |
| `gpt-mini` | GPT-5 Mini | $0.15 | $0.60 |
| `local` | Ollama (configurable) | $0.00 | $0.00 |

CLI-subscription aliases (`claude-cli`, `gemini-cli`, `codex-cli`, `ollama-cli`) are also available — see `common.py`.

## FAQ

**Do I need all API keys?** No. One provider is enough.

**How long does indexing take?** ~5-10 seconds per paper.

**Can I use a local embedding model?** Yes. Change `DEFAULT_EMBED_MODEL` in `researcher.py` to `"ollama/nomic-embed-text"`.

**How do I update the index?** Run indexing again — already-indexed papers are skipped by Zotero item key. Use `--force` to re-index everything.
