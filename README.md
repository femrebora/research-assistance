# research-assistant

[![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python\&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-A3E635)](LICENSE)
[![Web UI](https://img.shields.io/badge/web%20UI-Flask-000000?logo=flask\&logoColor=white)](https://flask.palletsprojects.com/)
[![Models](https://img.shields.io/badge/models-Claude%20%7C%20Gemini%20%7C%20DeepSeek%20%7C%20GPT--5-7C3AED)](#supported-models)

**research-assistant** is a local first academic research workspace for thesis helper, literature review, citation-aware drafting, paper discovery, model comparison, and transparent AI assisted research workflows.

It combines a Flask Web UI, Zotero-indexed retrieval, multi-model comparison, academic writing tools, AI usage disclosure logs, and PaperForge, a multi-agent paper drafting pipeline.

The goal is to help researchers work with their own papers, ask better questions, compare model outputs, write more structured drafts, and keep AI-assisted research transparent.

## Main features

<table>
  <thead>
    <tr>
      <th>Feature area</th>
      <th>What it does</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Zotero RAG</strong></td>
      <td>Indexes Zotero PDFs and lets you ask questions over your own academic library.</td>
    </tr>
    <tr>
      <td><strong>Literature Q&amp;A</strong></td>
      <td>Generates citation-aware answers from indexed papers.</td>
    </tr>
    <tr>
      <td><strong>Model comparison</strong></td>
      <td>Sends the same research question to multiple models and compares their answers side by side.</td>
    </tr>
    <tr>
      <td><strong>Academic writing tools</strong></td>
      <td>Supports outlining, critique, paraphrase checking, coherence review, claim verification, and citation auditing.</td>
    </tr>
    <tr>
      <td><strong>Paper discovery</strong></td>
      <td>Finds related papers through external discovery sources such as OpenAlex and Semantic Scholar.</td>
    </tr>
    <tr>
      <td><strong>Project workspace</strong></td>
      <td>Stores project title, research question, hypothesis, keywords, citation style, and supervisor notes.</td>
    </tr>
    <tr>
      <td><strong>Peer review simulation</strong></td>
      <td>Runs structural, methodological, and citation-focused review passes across multiple models.</td>
    </tr>
    <tr>
      <td><strong>Defense preparation</strong></td>
      <td>Generates thesis defense questions from multiple examiner personas.</td>
    </tr>
    <tr>
      <td><strong>PaperForge</strong></td>
      <td>Creates academic paper drafts from a codebase or research topic using a multi-agent workflow.</td>
    </tr>
    <tr>
      <td><strong>AI disclosure</strong></td>
      <td>Logs model usage and generates disclosure statements for thesis or manuscript workflows.</td>
    </tr>
  </tbody>
</table>

## Quick start

```bash
git clone https://github.com/femrebora/research-assistant
cd research-assistant
bash scripts/setup.sh
source ~/.venvs/thesis/bin/activate
ra-web
```

Open the Web UI:

```text
http://127.0.0.1:5050
```

The setup script creates a Python virtual environment, installs the package in editable mode, creates a `.env` file from `env.example`, and prepares the default local research folders.

Default locations:

<table>
  <thead>
    <tr>
      <th>Item</th>
      <th>Default path</th>
      <th>What it is used for</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Virtual environment</td>
      <td><code>~/.venvs/thesis</code></td>
      <td>Python environment used to run the app and CLI commands.</td>
    </tr>
    <tr>
      <td>Project workspace</td>
      <td><code>~/thesis</code></td>
      <td>Main local workspace for logs, drafts, project files, and research outputs.</td>
    </tr>
    <tr>
      <td>Model usage logs</td>
      <td><code>~/thesis/logs/</code></td>
      <td>Saved model calls used for AI disclosure and transparency.</td>
    </tr>
    <tr>
      <td>Zotero PDF storage</td>
      <td><code>~/Zotero/storage</code></td>
      <td>Local Zotero attachment folder used for PDF indexing.</td>
    </tr>
    <tr>
      <td>Application settings</td>
      <td><code>.env</code></td>
      <td>API keys, Zotero settings, provider commands, paths, and timeouts.</td>
    </tr>
  </tbody>
</table>

## First time setup checklist

After starting the Web UI, follow this order:

<table>
  <thead>
    <tr>
      <th>Step</th>
      <th>Where to go</th>
      <th>What to do</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td><code>/settings</code></td>
      <td>Add at least one model provider API key or configure a CLI provider.</td>
    </tr>
    <tr>
      <td>2</td>
      <td><code>/providers</code></td>
      <td>Test that the selected provider works before writing or indexing.</td>
    </tr>
    <tr>
      <td>3</td>
      <td><code>/settings</code></td>
      <td>Add Zotero user ID, Zotero API key, <code>THESIS_ROOT</code>, and <code>ZOTERO_STORAGE</code>.</td>
    </tr>
    <tr>
      <td>4</td>
      <td><code>/index</code></td>
      <td>Index Zotero PDFs so the Ask and Evidence tools can retrieve from your own papers.</td>
    </tr>
    <tr>
      <td>5</td>
      <td><code>/projects</code></td>
      <td>Create or update the active research project with title, research question, hypothesis, keywords, citation style, and supervisor notes.</td>
    </tr>
    <tr>
      <td>6</td>
      <td><code>/ask</code></td>
      <td>Ask a small test question to confirm that citations and retrieved evidence are working.</td>
    </tr>
  </tbody>
</table>

## Daily workflow

A simple daily workflow is:

```text
1. Start the environment
2. Open the Web UI
3. Check the active project
4. Ask or compare model answers using your indexed papers
5. Save useful outputs into the Workspace
6. Audit or verify claims before adding text to your thesis
7. Generate disclosure logs when needed
```

Commands:

```bash
cd research-assistant
source ~/.venvs/thesis/bin/activate
ra-web
```

Then open:

```text
http://127.0.0.1:5050
```

Use the Web UI for most work. Use the CLI when you want repeatable commands, scripting, or batch workflows.

## Configuration

You can configure the application from the browser:

```text
http://127.0.0.1:5050/settings
```

The settings page lets you edit API keys, Zotero configuration, provider commands, paths, and timeouts. Changes are written back to your `.env` file automatically.

You only need one model provider to start.

```bash
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...
```

For Zotero integration, configure these values from `/settings` or directly in `.env`:

```bash
ZOTERO_USER_ID=1234567
ZOTERO_API_KEY=...
THESIS_ROOT=/home/you/thesis
ZOTERO_STORAGE=/home/you/Zotero/storage
```

Check provider health from:

```text
http://127.0.0.1:5050/providers
```

Model calls are logged under:

```text
~/thesis/logs/
```

These logs can be used to prepare AI usage disclosure text for thesis, manuscript, or institutional transparency requirements.

## How to organize your work

The tool works best when each thesis, manuscript, or review article has a clear folder inside `THESIS_ROOT`.

Recommended structure:

```text
~/thesis/
├── projects/
│   └── my-thesis-project/
│       ├── drafts/
│       ├── notes/
│       ├── outlines/
│       ├── evidence/
│       ├── exports/
│       └── paperforge/
├── logs/
├── indexes/
└── disclosures/
```

Suggested use for each folder:

<table>
  <thead>
    <tr>
      <th>Folder</th>
      <th>Save here</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>drafts/</code></td>
      <td>Thesis chapters, manuscript sections, revised paragraphs, and long form writing.</td>
    </tr>
    <tr>
      <td><code>notes/</code></td>
      <td>Your own reading notes, supervisor comments, meeting notes, and research ideas.</td>
    </tr>
    <tr>
      <td><code>outlines/</code></td>
      <td>Generated outlines, chapter plans, article structures, and section maps.</td>
    </tr>
    <tr>
      <td><code>evidence/</code></td>
      <td>Important cited answers, claim verification outputs, citation audit results, and evidence tables.</td>
    </tr>
    <tr>
      <td><code>exports/</code></td>
      <td>Final copied outputs, disclosure text, report exports, and material prepared for submission.</td>
    </tr>
    <tr>
      <td><code>paperforge/</code></td>
      <td>PaperForge drafts, review article outputs, quality checks, and revision loop outputs.</td>
    </tr>
    <tr>
      <td><code>logs/</code></td>
      <td>Automatic model usage logs. Keep this folder if your thesis or journal requires AI disclosure.</td>
    </tr>
  </tbody>
</table>

You can keep the default `~/thesis` path, or change it from `/settings` by editing `THESIS_ROOT`.

## Where outputs are saved

research-assistant has three kinds of saved work:

<table>
  <thead>
    <tr>
      <th>Output type</th>
      <th>Where to find it</th>
      <th>How to use it later</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Saved Q&amp;A sessions</td>
      <td><code>/sessions</code></td>
      <td>Return to previous questions, review cited answers, and delete sessions you no longer need.</td>
    </tr>
    <tr>
      <td>Workspace files</td>
      <td><code>/workspace</code> and your <code>THESIS_ROOT</code> folder</td>
      <td>Continue writing, copy text into your thesis, or organize outputs into project folders.</td>
    </tr>
    <tr>
      <td>Project metadata</td>
      <td><code>/projects</code></td>
      <td>Reuse project title, research question, hypothesis, keywords, citation style, and supervisor notes across tools.</td>
    </tr>
    <tr>
      <td>Model logs</td>
      <td><code>~/thesis/logs/</code> by default</td>
      <td>Generate AI disclosure text and review which model was used for which task.</td>
    </tr>
    <tr>
      <td>PaperForge outputs</td>
      <td>The folder passed with <code>--output</code>, or the default output folder used by the module</td>
      <td>Review generated drafts, revision passes, and quality checks before using them in academic writing.</td>
    </tr>
    <tr>
      <td>Zotero indexed evidence</td>
      <td>Managed by the local index created from Zotero PDFs</td>
      <td>Use Ask, Evidence, Claim Verify, Audit, and Outline tools with citation aware retrieval.</td>
    </tr>
  </tbody>
</table>

## How to return to previous work

To continue a previous session:

```bash
cd research-assistant
source ~/.venvs/thesis/bin/activate
ra-web
```

Then:

<table>
  <thead>
    <tr>
      <th>Goal</th>
      <th>Go to</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Continue a saved question or answer</td>
      <td><code>/sessions</code></td>
    </tr>
    <tr>
      <td>Continue a thesis or manuscript file</td>
      <td><code>/workspace</code></td>
    </tr>
    <tr>
      <td>Check or change the active project</td>
      <td><code>/projects</code></td>
    </tr>
    <tr>
      <td>Check model usage and costs</td>
      <td><code>/orchestration</code></td>
    </tr>
    <tr>
      <td>Generate or review AI disclosure text</td>
      <td><code>ra-disclose</code> or the disclosure tools in the Web UI</td>
    </tr>
    <tr>
      <td>Run another Zotero indexing pass</td>
      <td><code>/index</code> or <code>ra-researcher index</code></td>
    </tr>
  </tbody>
</table>

Good practice:

```text
Before closing the app:
1. Copy important model outputs into a Workspace file.
2. Keep cited answers in Sessions if you may need the evidence trail later.
3. Export or save important drafts under the correct project folder.
4. Keep logs if you need transparent AI usage records.
```

## Safe use and backup

Do not commit private files, API keys, unpublished thesis drafts, Zotero PDFs, or model logs to a public GitHub repository.

Recommended backup items:

<table>
  <thead>
    <tr>
      <th>Back up</th>
      <th>Why</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>.env</code></td>
      <td>Contains your local configuration. Store it securely because it may contain API keys.</td>
    </tr>
    <tr>
      <td><code>THESIS_ROOT</code></td>
      <td>Contains your drafts, notes, outputs, logs, and project files.</td>
    </tr>
    <tr>
      <td>Zotero library</td>
      <td>Contains the papers and metadata used for citation aware retrieval.</td>
    </tr>
  </tbody>
</table>

A safe backup command for your thesis workspace is:

```bash
tar -czf thesis-backup-$(date +%Y%m%d).tar.gz ~/thesis
```

For sensitive work, use encrypted storage or a private backup location.

## Typical use cases

<table>
  <thead>
    <tr>
      <th>Task</th>
      <th>Recommended page or command</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Ask a question from your Zotero papers</td>
      <td><code>/ask</code> or <code>ra-researcher ask</code></td>
    </tr>
    <tr>
      <td>Compare model answers before trusting one answer</td>
      <td><code>/compare</code> or <code>ra-compare</code></td>
    </tr>
    <tr>
      <td>Build a thesis or manuscript outline</td>
      <td><code>/outline-recommender</code></td>
    </tr>
    <tr>
      <td>Check whether a claim is supported</td>
      <td><code>ra-claim-verify</code></td>
    </tr>
    <tr>
      <td>Review citation quality</td>
      <td><code>ra-audit</code></td>
    </tr>
    <tr>
      <td>Improve a paragraph without changing meaning</td>
      <td><code>ra-paraphrase</code> or paraphrase tools in the Web UI</td>
    </tr>
    <tr>
      <td>Prepare for thesis defense</td>
      <td><code>/defense</code></td>
    </tr>
    <tr>
      <td>Generate AI usage disclosure</td>
      <td><code>ra-disclose</code></td>
    </tr>
    <tr>
      <td>Generate a paper draft from a codebase or topic</td>
      <td><code>/paperforge</code>, <code>scripts/run_agentic.py</code>, or <code>scripts/run_review.py</code></td>
    </tr>
  </tbody>
</table>

## Troubleshooting

<table>
  <thead>
    <tr>
      <th>Problem</th>
      <th>What to check</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>The Web UI does not start</td>
      <td>Activate the environment with <code>source ~/.venvs/thesis/bin/activate</code>, then run <code>ra-web</code> again.</td>
    </tr>
    <tr>
      <td>A model provider fails</td>
      <td>Open <code>/providers</code>, check your API key in <code>/settings</code>, and confirm the selected provider alias is configured.</td>
    </tr>
    <tr>
      <td>Zotero papers are not found</td>
      <td>Check <code>ZOTERO_USER_ID</code>, <code>ZOTERO_API_KEY</code>, and <code>ZOTERO_STORAGE</code>. Then run indexing again from <code>/index</code>.</td>
    </tr>
    <tr>
      <td>Answers do not contain useful citations</td>
      <td>Index more relevant PDFs, ask a narrower question, or add stronger keywords to the active project.</td>
    </tr>
    <tr>
      <td>CLI provider times out</td>
      <td>Increase <code>CLI_TIMEOUT</code> in <code>/settings</code> or in <code>.env</code>.</td>
    </tr>
    <tr>
      <td>You cannot find old work</td>
      <td>Check <code>/sessions</code>, <code>/workspace</code>, the active project in <code>/projects</code>, and the folders under <code>THESIS_ROOT</code>.</td>
    </tr>
  </tbody>
</table>


## Web UI

<table>
  <thead>
    <tr>
      <th>Page</th>
      <th>Route</th>
      <th>Purpose</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Dashboard</td>
      <td><code>/</code></td>
      <td>View index statistics, quick ask, recent sessions, and active project information.</td>
    </tr>
    <tr>
      <td>Ask</td>
      <td><code>/ask</code></td>
      <td>Ask citation-aware questions against your indexed papers.</td>
    </tr>
    <tr>
      <td>Compare</td>
      <td><code>/compare</code></td>
      <td>Compare answers from different model providers on the same research question.</td>
    </tr>
    <tr>
      <td>Sessions</td>
      <td><code>/sessions</code></td>
      <td>Browse, review, and delete saved research Q&amp;A sessions.</td>
    </tr>
    <tr>
      <td>Index</td>
      <td><code>/index</code></td>
      <td>Index Zotero papers and track background indexing progress.</td>
    </tr>
    <tr>
      <td>Tools</td>
      <td><code>/tools/&lt;name&gt;</code></td>
      <td>Use CLI tools from browser forms without leaving the Web UI.</td>
    </tr>
    <tr>
      <td>Outline Recommender</td>
      <td><code>/outline-recommender</code></td>
      <td>Generate paper-type-aware outlines with evidence mapping and active project prefill.</td>
    </tr>
    <tr>
      <td>Projects</td>
      <td><code>/projects</code></td>
      <td>Manage project title, research question, hypothesis, keywords, citation style, and supervisor notes.</td>
    </tr>
    <tr>
      <td>Peer Review</td>
      <td><code>/peer-review</code></td>
      <td>Run structural, methodological, and citation-focused review passes across multiple models.</td>
    </tr>
    <tr>
      <td>Defense</td>
      <td><code>/defense</code></td>
      <td>Generate thesis defense questions from friendly, strict, methodological, statistical, and field-expert examiner personas.</td>
    </tr>
    <tr>
      <td>Orchestration</td>
      <td><code>/orchestration</code></td>
      <td>Monitor model calls, token usage, estimated cost, and daily usage trends.</td>
    </tr>
    <tr>
      <td>Prompt Library</td>
      <td><code>/prompts</code></td>
      <td>Use curated academic prompts with one-click copy or send-to-Ask actions.</td>
    </tr>
    <tr>
      <td>Workspace</td>
      <td><code>/workspace</code></td>
      <td>Edit project files, manage thesis text, and organize writing work.</td>
    </tr>
    <tr>
      <td>Settings</td>
      <td><code>/settings</code></td>
      <td>Configure API keys, Zotero details, paths, CLI provider commands, and timeouts.</td>
    </tr>
    <tr>
      <td>Providers</td>
      <td><code>/providers</code></td>
      <td>Test whether each configured model provider is working.</td>
    </tr>
    <tr>
      <td>PaperForge</td>
      <td><code>/paperforge</code></td>
      <td>Generate paper drafts from code or topics with live progress updates.</td>
    </tr>
  </tbody>
</table>

## PaperForge

**PaperForge** is the multi-agent paper generation pipeline. It produces academic papers from codebases or research topics with an interactive web UI, ZeroGPT-aware writing, publication-quality charts, and Research Assistant tool integration.

### Web UI

Start the server and open `http://localhost:5055/paperforge`:

```bash
./scripts/start.sh
```

The interactive UI guides you through 6 steps:

1. **Input** — code path + summary or research topic
2. **Generate** — Outline (RA) → Code Analyst → Writer → Paraphrase (RA), with real-time SSE progress
3. **Edit Draft** — per-section review with text selection, yellow highlighting, numbered feedback panels, and targeted revisions via Claude/DeepSeek
4. **Figures** — review generated charts, request regenerations with feedback
5. **Assess & Revise** — PF Assessor + RA Peer Review (structural, methodology, citation reviewers), automated revision loop
6. **Finalize** — Plagiarism Check + RA Claim Verify + RA External Match, download paper.md and paper.docx

Per-section features: Quick AI scoring, ZeroGPT checks with score persistence, version history with per-section revert (up to 10 versions), and state that survives server restarts.

### Pipeline

```
Outline (RA) → Code/Lit Analyst → Writer (+ structured FIG data)
    → Paraphrase (RA) → [Interactive Editing]
    → Assessor + Peer Review ×3 → Rewriter
    → Plagiarism + Claim Verify + External Match
    → Figure Gen (Chart MCP, 8 types) → Finalize + Disclose (RA)
```

### CLI entry points

<table>
  <thead>
    <tr><th>Script</th><th>Purpose</th></tr>
  </thead>
  <tbody>
    <tr><td><code>scripts/run_agentic.py</code></td><td>Generate paper from a codebase (single-pass, no UI).</td></tr>
    <tr><td><code>scripts/run_review.py</code></td><td>Generate review article from a topic via web research.</td></tr>
    <tr><td><code>scripts/generate_final_docx.py</code></td><td>Export a pipeline run to DOCX with embedded figures.</td></tr>
    <tr><td><code>agentic/quick_ai_score.py</code></td><td>Mechanical AI-text detection (no API calls, 7 checks).</td></tr>
    <tr><td><code>agentic/mcp_servers/chart_server.py</code></td><td>Chart MCP server: bar, grouped_bar, line, scatter, heatmap, timeline, pie, radar.</td></tr>
    <tr><td><code>agentic/mcp_servers/zerogpt_server.py</code></td><td>ZeroGPT MCP server: Playwright-based AI detection via zerogpt.com.</td></tr>
    <tr><td><code>agentic/mcp_servers/google_search_server.py</code></td><td>Search MCP: Brave Search API with DuckDuckGo fallback.</td></tr>
  </tbody>
</table>

### Key features

| Feature | Description |
|---|---|
| **AI-aware writing** | Writer prompt avoids ZeroGPT triggers (em dashes, formulaic phrases, uniform sentences). Per-section Quick AI scores + ZeroGPT checks. |
| **Structured figures** | Writer outputs `[FIG bar|title|categories|values]` format. Chart MCP renders 8 chart types at 300 DPI. |
| **RA integration** | Outline Recommender, Peer Review (3 reviewers), Claim Verify, External Match, Paraphrase, Disclose. |
| **State persistence** | All pipeline state on disk at `~/thesis/runs/<id>/`. Survives restarts. Atomic writes with per-job locking. |
| **DOCX export** | Times New Roman, embedded figures, AI-tell cleanup (**, em/en dashes stripped). |
| **Road-tested** | Generated a 7,600-word personalized medicine review (22% ZeroGPT) and a 25K-char EGFR MD simulation paper with 4 publication-quality charts. |

### CLI usage examples

```bash
# One-time cache setup
./scripts/run_agentic.py --refresh-style --domain bioinformatics
./scripts/run_agentic.py --refresh-artifacts

# Generate paper from codebase
./scripts/run_agentic.py /path/to/project --summary "What it does" --output /tmp/paper

# Generate review article
./scripts/run_review.py --topic "CRISPR-Based Therapeutics: Delivery Methods"

# Export pipeline run to DOCX with figures
./scripts/generate_final_docx.py <job_id> --charts /path/to/charts

# Quick AI score check
./agentic/quick_ai_score.py paper.md --json
```

## CLI usage

Everything available in the Web UI can also be used from the terminal.

<table>
  <thead>
    <tr>
      <th>Command</th>
      <th>Purpose</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>ra-researcher ask</code></td>
      <td>Ask a RAG-backed question with cited output.</td>
    </tr>
    <tr>
      <td><code>ra-researcher index</code></td>
      <td>Index Zotero PDFs.</td>
    </tr>
    <tr>
      <td><code>ra-compare</code></td>
      <td>Compare multiple model responses.</td>
    </tr>
    <tr>
      <td><code>ra-ask</code></td>
      <td>Ask a single model directly.</td>
    </tr>
    <tr>
      <td><code>ra-zot</code></td>
      <td>Search your Zotero library.</td>
    </tr>
    <tr>
      <td><code>ra-discover</code></td>
      <td>Find papers through OpenAlex and Semantic Scholar.</td>
    </tr>
    <tr>
      <td><code>ra-evidence</code></td>
      <td>Run evidence-focused cited queries.</td>
    </tr>
    <tr>
      <td><code>ra-outline-recommender</code></td>
      <td>Generate paper-type-aware outlines with evidence mapping.</td>
    </tr>
    <tr>
      <td><code>ra-ideas</code></td>
      <td>Create paragraph angles from evidence.</td>
    </tr>
    <tr>
      <td><code>ra-outline</code></td>
      <td>Create section outlines with citation stubs.</td>
    </tr>
    <tr>
      <td><code>ra-critique</code></td>
      <td>Critique a draft.</td>
    </tr>
    <tr>
      <td><code>ra-critic</code></td>
      <td>Run a writer and critic workflow.</td>
    </tr>
    <tr>
      <td><code>ra-paraphrase</code></td>
      <td>Run writer, paraphraser, and meaning checker workflow.</td>
    </tr>
    <tr>
      <td><code>ra-coherence</code></td>
      <td>Analyze chapter coherence.</td>
    </tr>
    <tr>
      <td><code>ra-audit</code></td>
      <td>Audit citation usage.</td>
    </tr>
    <tr>
      <td><code>ra-verify</code></td>
      <td>Resolve citekeys against a bibliography file.</td>
    </tr>
    <tr>
      <td><code>ra-claim-verify</code></td>
      <td>Check whether claims are supported by retrieved evidence.</td>
    </tr>
    <tr>
      <td><code>ra-originality</code></td>
      <td>Check internal and external originality signals.</td>
    </tr>
    <tr>
      <td><code>ra-disclose</code></td>
      <td>Generate an AI usage disclosure statement.</td>
    </tr>
    <tr>
      <td><code>ra-pipeline</code></td>
      <td>Run the full research writing pipeline.</td>
    </tr>
  </tbody>
</table>

Run any command with `--help` to see available options.

## Supported models

<table>
  <thead>
    <tr>
      <th>Alias</th>
      <th>Provider or model</th>
      <th>Recommended use</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>claude</code></td>
      <td>Claude</td>
      <td>Long-form reasoning, critique, and revision.</td>
    </tr>
    <tr>
      <td><code>sonnet</code></td>
      <td>Claude Sonnet</td>
      <td>Balanced academic writing and review workflows.</td>
    </tr>
    <tr>
      <td><code>haiku</code></td>
      <td>Claude Haiku</td>
      <td>Fast lightweight tasks.</td>
    </tr>
    <tr>
      <td><code>gemini</code></td>
      <td>Gemini</td>
      <td>Long context, research synthesis, and multimodal workflows.</td>
    </tr>
    <tr>
      <td><code>flash</code></td>
      <td>Gemini Flash</td>
      <td>Fast and lower-cost processing.</td>
    </tr>
    <tr>
      <td><code>deepseek</code></td>
      <td>DeepSeek Chat</td>
      <td>Draft generation and general writing tasks.</td>
    </tr>
    <tr>
      <td><code>gpt</code></td>
      <td>GPT</td>
      <td>General reasoning, writing, and structured output.</td>
    </tr>
    <tr>
      <td><code>gpt-mini</code></td>
      <td>GPT Mini</td>
      <td>Lower-cost general tasks.</td>
    </tr>
    <tr>
      <td><code>local</code></td>
      <td>Ollama</td>
      <td>Local model workflows.</td>
    </tr>
  </tbody>
</table>

CLI subscription aliases such as `claude-cli`, `gemini-cli`, `codex-cli`, and `ollama-cli` can also be configured.

## Example workflows

### Ask a question over your Zotero library

```bash
ra-researcher ask "What are the main mechanisms of TRAIL resistance in glioblastoma?"
```

### Compare multiple models

```bash
ra-compare "Summarize the evidence for metabolic rewiring in glioblastoma resistance."
```

### Generate an outline

```bash
ra-outline-recommender
```

### Audit citations

```bash
ra-audit draft.md
```

### Generate AI disclosure text

```bash
ra-disclose
```

## When to use research-assistant

<table>
  <thead>
    <tr>
      <th>Use case</th>
      <th>Why it helps</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Thesis helper</td>
      <td>Organizes papers, project context, prompts, drafts, and model outputs in one place.</td>
    </tr>
    <tr>
      <td>Literature review</td>
      <td>Combines Zotero indexing, cited Q&amp;A, paper discovery, and outline generation.</td>
    </tr>
    <tr>
      <td>Academic drafting</td>
      <td>Supports critique, paraphrase checking, coherence analysis, and citation auditing.</td>
    </tr>
    <tr>
      <td>Research software papers</td>
      <td>Can turn codebase context into a structured academic paper draft.</td>
    </tr>
    <tr>
      <td>Model evaluation</td>
      <td>Compares multiple models before relying on one output.</td>
    </tr>
    <tr>
      <td>AI transparency</td>
      <td>Keeps model usage logs and helps prepare disclosure statements.</td>
    </tr>
  </tbody>
</table>

## Notes on responsible use

research-assistant is designed to support research, not replace academic judgment. Always verify claims, check citations, review generated text carefully, and follow the AI use policies of your university, journal, conference, or institution.

AI-assisted writing should be disclosed when required. The built-in logging and disclosure tools are intended to make this process easier.

## FAQ

### Do I need all API keys?

No. One provider is enough to start. More providers are useful for comparison and multi-agent workflows.

### Do I need Zotero?

Zotero is recommended if you want citation-aware Q&A over your own papers. Some writing and model comparison tools can still be used without Zotero.

### How long does indexing take?

Indexing time depends on the number and size of PDFs. Already indexed papers are skipped by Zotero item key unless re-indexing is forced.

### Can I use local models?

Yes. Ollama can be configured for local model workflows.

### Can I use a local embedding model?

Yes. For example, you can configure a local embedding model such as `ollama/nomic-embed-text` if your setup supports it.

### Is this a replacement for a supervisor or peer reviewer?

No. research-assistant helps with organization, drafting, evidence checking, and model comparison. Final academic judgment and responsibility remain with the researcher.

## Project philosophy

<table>
  <thead>
    <tr>
      <th>Principle</th>
      <th>Meaning</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Local-first</td>
      <td>Your research workspace, indexed files, logs, and drafts stay organized on your own machine.</td>
    </tr>
    <tr>
      <td>Evidence-aware</td>
      <td>The tool is designed to work with your own papers and make retrieved evidence visible.</td>
    </tr>
    <tr>
      <td>Transparent AI use</td>
      <td>AI assistance should be logged, reviewable, and explainable in academic workflows.</td>
    </tr>
  </tbody>
</table>

## License

MIT License
