# research-assistant

[![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python\&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-A3E635)](LICENSE)
[![Web UI](https://img.shields.io/badge/web%20UI-Flask-000000?logo=flask\&logoColor=white)](https://flask.palletsprojects.com/)
[![Models](https://img.shields.io/badge/models-Claude%20%7C%20Gemini%20%7C%20DeepSeek%20%7C%20GPT--5-7C3AED)](#supported-models)

**research-assistant** is a local first academic research workspace for thesis writing, literature review, citation-aware drafting, paper discovery, model comparison, and transparent AI assisted research workflows.

It combines a Flask Web UI, Zotero-indexed retrieval, multi-model comparison, academic writing tools, AI usage disclosure logs, and PaperForge, a multi-agent paper drafting pipeline.

The goal is to help researchers work with their own papers, ask better questions, compare model outputs, write more structured drafts, and keep AI-assisted research transparent.

<!--
## Demo

<p align="center">
  <img src="docs/assets/research-assistant-demo.gif" alt="research-assistant Web UI demo" width="900">
</p>
-->

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
bash setup.sh
source ~/.venvs/thesis/bin/activate
ra-web
```

Open the Web UI:

```text
http://127.0.0.1:5050
```

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

**PaperForge** is the multi-agent paper drafting module of research-assistant. It can generate structured academic drafts from either a codebase or a research topic.

<table>
  <thead>
    <tr>
      <th>Script</th>
      <th>Purpose</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>run_agentic.py</code></td>
      <td>Generate an academic paper draft from a codebase.</td>
    </tr>
    <tr>
      <td><code>run_review.py</code></td>
      <td>Generate a review article draft from a research topic using autonomous literature discovery.</td>
    </tr>
    <tr>
      <td><code>agentic/quick_ai_score.py</code></td>
      <td>Run mechanical checks for AI-like writing patterns without making LLM calls.</td>
    </tr>
  </tbody>
</table>

### PaperForge workflow

```text
Codebase or research topic
        ↓
Research or code analysis
        ↓
Draft generation
        ↓
Section assessment
        ↓
Revision loop
        ↓
Quality and similarity checks
        ↓
Final draft
```

For review articles, the code analysis step is replaced by literature research. The workflow can search academic sources and collect background material before drafting.

### PaperForge usage

```bash
# One-time cache setup
./run_agentic.py --refresh-style --domain bioinformatics
./run_agentic.py --refresh-artifacts

# Generate a paper draft from a codebase
./run_agentic.py /path/to/project --summary "What it does" --output /tmp/paper

# Generate a review article draft from a topic
./run_review.py --topic "CRISPR-Based Therapeutics: Delivery Methods"

# Check a paper for AI-like writing patterns
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
