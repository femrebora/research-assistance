# research-assistant

[![python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-A3E635)](LICENSE)
[![flask](https://img.shields.io/badge/web%20UI-Flask-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![models](https://img.shields.io/badge/models-Claude%20%7C%20Gemini%20%7C%20DeepSeek%20%7C%20GPT--5-7C3AED)](#supported-models)

AI powered research toolkit for thesis writing. Ask questions against your Zotero library, generate paper outlines, run peer reviews, simulate your defense, and generate full papers from code or topics. Everything works through a Flask web UI or CLI.

## Quick start

```bash
git clone https://github.com/femrebora/research-assistant
cd research-assistant
./setup.sh
```

Edit `.env` with at least one API key:

```bash
ANTHROPIC_API_KEY=sk-ant-...
# or GEMINI_API_KEY=... / DEEPSEEK_API_KEY=sk-... / OPENAI_API_KEY=sk-...
```

Then launch:

```bash
source ~/.venvs/thesis/bin/activate
ra-web          # open http://127.0.0.1:5050
```

## Web UI

All features are available at `http://127.0.0.1:5050`.

### Ask and search

| Page | What it does |
|---|---|
| `/` Dashboard | Index stats, quick ask box, active project banner |
| `/ask` | RAG backed Q&A against your indexed papers with citations |
| `/compare` | Same question answered by multiple models side by side |
| `/sessions` | Browse and manage saved Q&A sessions |

### Writing tools

| Page | What it does |
|---|---|
| `/outline-recommender` | Structured outline with evidence mapping, pre-filled from your active project |
| `/tools/outline` | Section outline with citation stubs |
| `/tools/critique` | Structural and argument feedback on a draft |
| `/tools/critic` | Writer + critic pipeline |
| `/tools/paraphrase` | Writer, paraphraser, checker pipeline |
| `/tools/coherence` | Chapter coherence analysis |

### Review and defense

| Page | What it does |
|---|---|
| `/peer-review` | Parallel structural, methodology, and citation reviewers across multiple models |
| `/defense` | Jury questions from 5 examiner personas (supervisor, external reviewer, methodologist, statistician, field expert) |

### Verification

| Page | What it does |
|---|---|
| `/tools/originality` | Originality check against internal RAG and OpenAlex / Crossref |
| `/tools/audit` | Citation audit |
| `/tools/verify` | Citekey resolution against your .bib file |
| `/tools/claim-verify` | Per-claim support audit |
| `/tools/disclose` | AI usage disclosure statement |

### Discovery

| Page | What it does |
|---|---|
| `/tools/discover` | Find papers via OpenAlex / Semantic Scholar |
| `/tools/evidence` | PaperQA2 cited evidence query |
| `/tools/zot` | Search your Zotero library |

### PaperForge (multi-agent paper generation)

PaperForge generates full academic papers using 7 specialized agents across 3 LLM backends.

| Mode | What it does |
|---|---|
| Code to Paper | Generate a paper from your codebase (`run_agentic.py`) |
| Topic to Review | Autonomous web research + review article (`run_review.py`) |
| AI Detection | 7 mechanical checks, 0-10 score, no LLM calls (`quick_ai_score.py`) |

```bash
# Generate a paper from a codebase
./run_agentic.py /path/to/project --summary "What it does" --output /tmp/paper

# Generate a review article
./run_review.py --topic "CRISPR-Based Therapeutics: Delivery Methods"

# Check a paper for AI generated patterns
./quick_ai_score.py paper.md --json
```

Pipeline: `Code Analyst -> Writer -> Assessor -> Rewriter (loops up to 3x) -> Plagiarism Check -> Figure Gen -> Supervisor`. For review mode, Code Analyst becomes Literature Researcher which searches OpenAlex and DuckDuckGo autonomously.

### Projects and workspace

| Page | What it does |
|---|---|
| `/projects` | Create projects with title, research question, hypothesis, keywords, citation style |
| `/projects/<slug>/activate` | Set active project (context injected into peer review, defense, and outline recommender) |
| `/workspace` | Full text editor with per-project file management |
| `/orchestration` | Model usage dashboard: calls, tokens, cost, daily spend |
| `/prompts` | 10 curated academic prompts, one click copy or send to Ask |
| `/index` | Background Zotero PDF indexing with live progress |

## CLI

All tools work from the terminal too. Run any command with `--help`.

### Ask and search

| Command | What it does |
|---|---|
| `ra-ask "question"` | Single model Q&A |
| `ra-compare "question"` | Multi model comparison |
| `ra-researcher ask "question"` | RAG question with cited answer |
| `ra-researcher index` | Index Zotero PDFs for RAG |
| `ra-zot "query"` | Search your Zotero library |
| `ra-discover "topic"` | Find papers via OpenAlex / Semantic Scholar |
| `ra-evidence "claim"` | PaperQA2 cited evidence query |

### Writing

| Command | What it does |
|---|---|
| `ra-outline "topic"` | Section outline with citation stubs |
| `ra-outline-recommender "topic"` | Paper-type aware outline with evidence mapping |
| `ra-ideas "topic"` | Paragraph angles from evidence |
| `ra-critique file.md` | Draft critique with structural feedback |
| `ra-critic file.md` | Writer + critic pipeline |
| `ra-paraphrase file.md` | Writer, paraphraser, checker pipeline |
| `ra-coherence chapter/` | Chapter coherence analysis |

### Verification

| Command | What it does |
|---|---|
| `ra-audit file.md` | Citation audit |
| `ra-verify file.md` | Citekey resolution against .bib |
| `ra-claim-verify file.md` | Per-claim support audit |
| `ra-originality file.md` | Originality check (internal + OpenAlex / Crossref) |
| `ra-disclose` | AI usage disclosure statement |
| `ra-pipeline` | Full end to end orchestrator |

## Zotero integration (optional)

For RAG backed Q&A, add these to `.env`:

```bash
ZOTERO_USER_ID=1234567
ZOTERO_API_KEY=...
ZOTERO_STORAGE=/home/you/Zotero/storage
THESIS_ROOT=/home/you/thesis       # default: ~/thesis
```

Then index from the web UI at `/index` or run `ra-researcher index`. Already indexed papers are skipped. Use `--force` to re-index everything. Indexing takes about 5-10 seconds per paper.

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

## FAQ

**Do I need all API keys?** No, one provider is enough. PaperForge works best with 2-3 providers since different agents use different models.

**How long does indexing take?** About 5-10 seconds per paper. Already indexed papers are skipped automatically.

**Can I use a local embedding model?** Yes. Set `DEFAULT_EMBED_MODEL` in `researcher.py` to `"ollama/nomic-embed-text"`.

**Where are model call logs stored?** `~/thesis/logs/` in JSONL format. Useful for disclosure statements.

**What does a PaperForge run cost?** About $1.50-$2.00 per full paper generation.
