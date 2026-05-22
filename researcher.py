#!/usr/bin/env python3
"""researcher.py — RAG-powered research assistant over your Zotero PDF library.

Index your Zotero PDFs into a local vector store, then ask research questions
and get cited, paraphrase-ready answers.

Usage:
    ./researcher.py index [--collection NAME] [--limit N] [--force]
    ./researcher.py ask "QUESTION" [--k 20] [--threshold 0.3] [--model claude] [--save NAME]
    ./researcher.py sessions [--view NAME|last]
    ./researcher.py stats
"""
from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
import pdfplumber
from rich.console import Console
from rich.markdown import Markdown
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
)
from rich.table import Table

from common import MODELS, THESIS_ROOT, ask_model

console = Console()

# ── Configuration ────────────────────────────────────────────────────────────

DEFAULT_EMBED_MODEL = "openai/text-embedding-3-small"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 200
MAX_CHUNKS_PER_SOURCE = 3
DEFAULT_K = 20
DEFAULT_THRESHOLD = 0.35

CHROMA_DIR = THESIS_ROOT / "chroma_db"
SESSION_DIR = THESIS_ROOT / "research_sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)

# ── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a research assistant helping with a master's thesis.
Answer using ONLY the provided source excerpts below. Follow these rules:

1. FORMAT: Present findings as bulleted evidence points with [@citekey] citations.
   Write in note-taking style that the author can paraphrase in their own words.
   Do NOT write polished prose or paragraphs ready to copy-paste.

2. CITATIONS: Cite every factual claim with [@citekey] from the Sources list.
   If multiple sources support a point, cite all: [@smith2024; @jones2023].
   If no source supports a claim, do not make it.

3. SCOPE: Only answer from the provided excerpts. If they lack sufficient
   information, say so explicitly rather than guessing or using outside knowledge.

4. CONFLICTS: Note when sources disagree. Present both sides with citations.
   Example: "Source A claims X [@a], while source B finds Y [@b]."

5. QUALITY: Mark well-supported findings (2+ sources) vs single-source findings.
   Flag claims needing additional verification with [needs verification].

{context}"""

# ── Zotero helpers ───────────────────────────────────────────────────────────

try:
    from pyzotero import zotero as _zotero_mod

    def _get_zotero_client():
        user_id = os.getenv("ZOTERO_USER_ID")
        api_key = os.getenv("ZOTERO_API_KEY")
        if not user_id or not api_key:
            console.print(
                "[red]Missing ZOTERO_USER_ID or ZOTERO_API_KEY in environment.[/red]"
            )
            sys.exit(1)
        return _zotero_mod.Zotero(user_id, "user", api_key)

    _ZOTERO_AVAILABLE = True
except ImportError:
    _ZOTERO_AVAILABLE = False


def _extract_citekey(item_data: dict) -> Optional[str]:
    extra = item_data.get("extra", "") or ""
    for line in extra.splitlines():
        if line.lower().startswith("citation key:"):
            return line.split(":", 1)[1].strip()
    return item_data.get("citekey")


def _extract_metadata(item_data: dict) -> dict:
    creators = item_data.get("creators", [])
    last_names = [c.get("lastName", "") for c in creators if c.get("lastName")]
    if len(last_names) == 0:
        authors_short = ""
    elif len(last_names) == 1:
        authors_short = last_names[0]
    elif len(last_names) == 2:
        authors_short = f"{last_names[0]} & {last_names[1]}"
    else:
        authors_short = f"{last_names[0]} et al."

    return {
        "title": item_data.get("title", ""),
        "authors_short": authors_short,
        "year": (item_data.get("date", "") or "")[:4],
        "doi": item_data.get("DOI", "") or "",
        "item_type": item_data.get("itemType", ""),
    }


def _find_pdf_attachment(zot, item_key: str) -> Optional[dict]:
    try:
        children = zot.children(item_key)
    except Exception:
        return None
    for child in children:
        data = child.get("data", {})
        if data.get("contentType") == "application/pdf":
            return data
    return None


def _resolve_pdf_path(item_key: str, filename: str) -> Optional[Path]:
    storage = os.getenv("ZOTERO_STORAGE")
    if not storage:
        return None
    path = Path(storage).expanduser() / item_key / filename
    return path if path.exists() else None


# ── PDF text extraction ──────────────────────────────────────────────────────


def _extract_pdf_text(pdf_path: Path) -> Optional[str]:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        if not pages:
            return None
        return "\n\n".join(pages)
    except Exception:
        return None


# ── Text chunking ────────────────────────────────────────────────────────────


def chunk_text(
    text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    if overlap >= size:
        raise ValueError(f"Overlap ({overlap}) must be less than chunk size ({size})")
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunk = text[start:end]

        if end < len(text):
            last_period = chunk.rfind(". ")
            last_newline = chunk.rfind("\n\n")
            last_break = max(last_period, last_newline)
            if last_break > size // 2:
                end = start + last_break + 1
                chunk = text[start:end]

        stripped = chunk.strip()
        if stripped:
            chunks.append(stripped)
        start = end - overlap if end < len(text) else len(text)

    return chunks


# ── Embedding ────────────────────────────────────────────────────────────────

def _embed_texts(
    texts: list[str],
    model: str = DEFAULT_EMBED_MODEL,
    max_retries: int = 3,
) -> list[list[float]]:
    import litellm as _litellm

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = _litellm.embedding(model=model, input=texts)
            return [d["embedding"] for d in response.data]  # type: ignore[index]
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(2 ** attempt)

    raise RuntimeError(
        f"All {max_retries} embedding retries failed. Last error: {last_error}"
    )


def _embed_single(text: str, model: str = DEFAULT_EMBED_MODEL) -> list[float]:
    return _embed_texts([text], model=model)[0]


# ── ChromaDB management ──────────────────────────────────────────────────────

try:
    import chromadb as _chromadb

    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False

COLLECTION_NAME = "thesis_papers"


def _get_chroma_client():
    if not _CHROMA_AVAILABLE:
        raise RuntimeError("chromadb not installed. Run: pip install chromadb")
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return _chromadb.PersistentClient(path=str(CHROMA_DIR))


def _get_collection(client=None, name: str = COLLECTION_NAME):
    if client is None:
        client = _get_chroma_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def _store_index_meta(collection, meta: dict) -> None:
    meta["indexed_at"] = datetime.now(tz=timezone.utc).isoformat()
    collection.upsert(
        ids=["__index_meta__"],
        documents=[""],
        metadatas=[meta],
    )


def _get_index_meta(collection) -> Optional[dict]:
    try:
        result = collection.get(ids=["__index_meta__"], include=["metadatas"])
        metas = result.get("metadatas", [])
        return metas[0] if metas else None
    except Exception:
        return None


def _is_document_indexed(collection, zotero_key: str) -> bool:
    try:
        result = collection.get(
            where={"zotero_key": zotero_key},
            limit=1,
            include=[],
        )
        return len(result.get("ids", [])) > 0
    except Exception:
        return False


def _remove_document(collection, zotero_key: str) -> None:
    try:
        existing = collection.get(
            where={"zotero_key": zotero_key},
            include=["metadatas"],
        )
        ids = existing.get("ids", [])
        if ids:
            collection.delete(ids=ids)
    except Exception:
        console.print(
            f"[yellow]Warning: could not remove existing chunks for {zotero_key}[/yellow]"
        )


def _get_index_stats(collection) -> dict:
    index_meta = _get_index_meta(collection) or {}

    try:
        chunk_count = collection.count()
    except Exception:
        chunk_count = 0

    docs_count = index_meta.get("total_documents", 0)

    return {
        "documents": docs_count,
        "chunks": chunk_count,
        "index_meta": index_meta,
    }


# ── Indexing orchestration ───────────────────────────────────────────────────


def _process_item(
    zot,
    item: dict,
    collection,
    force: bool,
    embedding_model: str,
    chunk_size: int,
    stats: dict,
) -> None:
    """Process a single Zotero item: extract PDF, chunk, embed, store."""
    item_data = item.get("data", {})
    item_key = item_data.get("key", "")
    item_title = item_data.get("title", "Unknown")[:60]

    # Check if already indexed
    if not force and _is_document_indexed(collection, item_key):
        stats["skipped"] += 1
        return

    # Find PDF attachment
    pdf_data = _find_pdf_attachment(zot, item_key)
    if not pdf_data:
        return

    stats["with_pdfs"] += 1
    filename = pdf_data.get("filename", "")
    pdf_path = _resolve_pdf_path(item_key, filename)

    if not pdf_path:
        stats["failed"] += 1
        return

    # Extract text
    text = _extract_pdf_text(pdf_path)
    if not text:
        stats["failed"] += 1
        return

    # Chunk
    chunks = chunk_text(text, size=chunk_size)
    if not chunks:
        stats["failed"] += 1
        return

    # Metadata
    citekey = _extract_citekey(item_data)
    meta = _extract_metadata(item_data)

    # Remove existing chunks if forcing re-index
    if force:
        _remove_document(collection, item_key)

    # Embed and store
    try:
        embeddings = _embed_texts(chunks, model=embedding_model)
    except Exception:
        stats["failed"] += 1
        return

    ids = [f"{item_key}_chunk_{i:04d}" for i in range(len(chunks))]
    metadatas = [
        {
            "zotero_key": item_key,
            "citekey": citekey or "",
            "title": meta["title"],
            "authors_short": meta["authors_short"],
            "year": meta["year"],
            "doi": meta["doi"],
            "item_type": meta["item_type"],
            "chunk_index": i,
            "total_chunks": len(chunks),
            "source_file": f"{item_key}/{filename}",
            "date_indexed": datetime.now(tz=timezone.utc).isoformat(),
        }
        for i in range(len(chunks))
    ]

    try:
        collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        stats["indexed"] += 1
        stats["total_chunks"] += len(chunks)
    except Exception:
        stats["failed"] += 1


def index_zotero_papers(
    collection_name: Optional[str] = None,
    limit: Optional[int] = None,
    force: bool = False,
    embedding_model: str = DEFAULT_EMBED_MODEL,
    chunk_size: int = CHUNK_SIZE,
) -> dict:
    """Index Zotero PDFs into ChromaDB. Returns summary dict."""
    if not _ZOTERO_AVAILABLE:
        console.print("[red]pyzotero not installed. Run: pip install pyzotero[/red]")
        sys.exit(1)

    zot = _get_zotero_client()
    client = _get_chroma_client()
    collection = _get_collection(client)

    storage = os.getenv("ZOTERO_STORAGE")
    if not storage or not Path(storage).expanduser().exists():
        console.print(
            "[red]ZOTERO_STORAGE not set or doesn't exist.[/red]\n"
            "Set it in .env to your Zotero storage folder, e.g. ~/Zotero/storage"
        )
        sys.exit(1)

    # Fetch items
    if collection_name:
        key, name = _find_collection_key(zot, collection_name)
        if not key:
            console.print(f"[red]No collection matching '{collection_name}'[/red]")
            sys.exit(1)
        console.print(f"[dim]Searching in collection: {name}[/dim]")
        items = zot.collection_items(key, limit=limit or 9999)
    else:
        items = zot.top(limit=limit or 9999)

    items_list = list(items)
    console.print(f"[dim]Found {len(items_list)} items in Zotero[/dim]\n")

    stats = {
        "total_items": len(items_list),
        "with_pdfs": 0,
        "indexed": 0,
        "skipped": 0,
        "failed": 0,
        "total_chunks": 0,
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Indexing papers...", total=len(items_list))

        for item in items_list:
            item_title = item.get("data", {}).get("title", "Unknown")[:60]
            progress.update(task, description=f"[cyan]{item_title}...")

            _process_item(zot, item, collection, force, embedding_model, chunk_size, stats)
            progress.advance(task)

    # Store index metadata
    _store_index_meta(
        collection,
        {
            "embedding_model": embedding_model,
            "chunk_size": chunk_size,
            "chunk_overlap": CHUNK_OVERLAP,
            "total_documents": stats["indexed"],
            "total_chunks": stats["total_chunks"],
        },
    )

    return stats


def _find_collection_key(zot, name: str) -> tuple[Optional[str], Optional[str]]:
    for c in zot.collections():
        if name.lower() in c["data"]["name"].lower():
            return c["key"], c["data"]["name"]
    return None, None


# ── Retrieval ────────────────────────────────────────────────────────────────


def retrieve_chunks(
    question: str,
    collection=None,
    k: int = DEFAULT_K,
    threshold: float = DEFAULT_THRESHOLD,
    embedding_model: str = DEFAULT_EMBED_MODEL,
) -> list[dict]:
    """Retrieve relevant chunks for a question. Returns list of result dicts."""
    if collection is None:
        collection = _get_collection()

    q_embedding = _embed_single(question, model=embedding_model)

    try:
        results = collection.query(
            query_embeddings=[q_embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        console.print(f"[red]Query failed: {e}[/red]")
        return []

    combined = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    for doc, meta, dist in zip(docs, metas, dists):
        if doc and meta and dist is not None:
            similarity = 1.0 - dist
            if similarity >= threshold:
                combined.append(
                    {
                        "text": doc,
                        "metadata": meta,
                        "similarity": round(similarity, 4),
                    }
                )

    return combined


def deduplicate_by_source(
    results: list[dict], max_per_source: int = MAX_CHUNKS_PER_SOURCE
) -> list[dict]:
    """Keep top N chunks per source, sorted by similarity."""
    by_source: dict[str, list[dict]] = {}
    for r in results:
        key = r["metadata"].get("zotero_key", "unknown")
        by_source.setdefault(key, []).append(r)

    deduped = []
    for chunks in by_source.values():
        chunks.sort(key=lambda x: x["similarity"], reverse=True)
        deduped.extend(chunks[:max_per_source])

    deduped.sort(key=lambda x: x["similarity"], reverse=True)
    return deduped


def build_context(results: list[dict]) -> str:
    """Build a formatted context block from retrieval results."""
    if not results:
        return "## Sources\n\n(No relevant sources found.)\n\n## Relevant Excerpts\n\n(None.)"

    # Gather unique sources
    seen = {}
    source_list = []
    for r in results:
        key = r["metadata"].get("zotero_key", "")
        if key not in seen:
            meta = r["metadata"]
            citekey = meta.get("citekey", "")
            title = meta.get("title", "Unknown")
            year = meta.get("year", "")
            authors = meta.get("authors_short", "")
            source_list.append((citekey, title, year, authors))
            seen[key] = len(source_list)  # 1-based index

    # Sources header
    lines = ["## Sources"]
    for i, (citekey, title, year, authors) in enumerate(source_list, 1):
        cite_str = f"@{citekey}" if citekey else f"source-{i}"
        year_str = f" ({year})" if year else ""
        author_str = f"{authors} — " if authors else ""
        lines.append(f"[{i}] {cite_str} — {author_str}\"{title}\"{year_str}")

    # Excerpts
    lines.append("")
    lines.append("## Relevant Excerpts")
    lines.append("")
    for r in results:
        meta = r["metadata"]
        key = meta.get("zotero_key", "")
        src_num = seen.get(key, "?")
        citekey = meta.get("citekey", "")
        cite_str = f"@{citekey}" if citekey else f"[source-{src_num}]"
        similarity = r["similarity"]
        lines.append(f"[{src_num}] {cite_str} (relevance: {similarity:.2f})")
        excerpt = r["text"][:600]
        if len(r["text"]) > 600:
            excerpt += " [...truncated]"
        lines.append(f"> {excerpt}")
        lines.append("")

    return "\n".join(lines)


# ── Answer generation ────────────────────────────────────────────────────────


def ask_research_question(
    question: str,
    model: str = "claude",
    temperature: float = 0.3,
    k: int = DEFAULT_K,
    threshold: float = DEFAULT_THRESHOLD,
    embedding_model: str = DEFAULT_EMBED_MODEL,
    collection=None,
) -> dict:
    """Full RAG pipeline: retrieve → build context → ask model. Returns result dict."""
    if collection is None:
        collection = _get_collection()

    console.print(f"[dim]→ Retrieving up to {k} chunks (threshold: {threshold})...[/dim]")

    results = retrieve_chunks(
        question,
        collection=collection,
        k=k,
        threshold=threshold,
        embedding_model=embedding_model,
    )

    if not results:
        return {
            "answer": "No sufficiently relevant passages found in your indexed papers. "
            "Try broadening your question, lowering the threshold, or indexing more documents.",
            "sources": [],
            "model": MODELS.get(model, model),
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
        }

    deduped = deduplicate_by_source(results)
    context = build_context(deduped)
    system = SYSTEM_PROMPT.format(context=context)

    console.print(
        f"[dim]→ {len(deduped)} chunks from {len(set(r['metadata'].get('zotero_key', '') for r in deduped))} sources → {model}[/dim]\n"
    )

    result = ask_model(
        question,
        model=model,
        system=system,
        temperature=temperature,
    )

    # Build source list for session persistence
    seen = {}
    sources = []
    for r in deduped:
        meta = r["metadata"]
        key = meta.get("zotero_key", "")
        if key not in seen:
            citekey = meta.get("citekey", "")
            sources.append(
                {
                    "citekey": citekey,
                    "title": meta.get("title", ""),
                    "authors_short": meta.get("authors_short", ""),
                    "year": meta.get("year", ""),
                    "similarity": r["similarity"],
                }
            )
            seen[key] = True

    return {
        "answer": result["text"],
        "sources": sources,
        "model": MODELS.get(model, model),
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "cost": result.get("cost", 0.0),
        "k_retrieved": k,
        "threshold": threshold,
        "embedding_model": embedding_model,
    }


def compare_research_question(
    question: str,
    models: list[str],
    temperature: float = 0.3,
    k: int = DEFAULT_K,
    threshold: float = DEFAULT_THRESHOLD,
    embedding_model: str = DEFAULT_EMBED_MODEL,
    collection=None,
) -> dict[str, dict]:
    """Run the same RAG query against multiple models in parallel. Returns {model_name: result_dict}."""
    if collection is None:
        collection = _get_collection()

    console.print(f"[dim]→ Retrieving up to {k} chunks (threshold: {threshold})...[/dim]")

    results = retrieve_chunks(
        question,
        collection=collection,
        k=k,
        threshold=threshold,
        embedding_model=embedding_model,
    )

    if not results:
        empty = {
            m: {
                "answer": "No sufficiently relevant passages found.",
                "sources": [],
                "model": MODELS.get(m, m),
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0,
            }
            for m in models
        }
        return empty

    deduped = deduplicate_by_source(results)
    context = build_context(deduped)
    system = SYSTEM_PROMPT.format(context=context)

    # Build source list once
    seen = {}
    sources = []
    for r in deduped:
        meta = r["metadata"]
        key = meta.get("zotero_key", "")
        if key not in seen:
            sources.append(
                {
                    "citekey": meta.get("citekey", ""),
                    "title": meta.get("title", ""),
                    "authors_short": meta.get("authors_short", ""),
                    "year": meta.get("year", ""),
                    "similarity": r["similarity"],
                }
            )
            seen[key] = True

    source_count = len(set(r["metadata"].get("zotero_key", "") for r in deduped))
    console.print(
        f"[dim]→ {len(deduped)} chunks from {source_count} sources → comparing {len(models)} models[/dim]\n"
    )

    # Parallel model calls
    def _call_one(model: str) -> tuple[str, dict]:
        try:
            result = ask_model(question, model=model, system=system, temperature=temperature)
            return model, {
                "answer": result["text"],
                "sources": sources,
                "model": MODELS.get(model, model),
                "input_tokens": result.get("input_tokens", 0),
                "output_tokens": result.get("output_tokens", 0),
                "cost": result.get("cost", 0.0),
            }
        except Exception as e:
            return model, {
                "answer": f"Error: {e}",
                "sources": sources,
                "model": MODELS.get(model, model),
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0,
            }

    outcomes: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=len(models)) as executor:
        futures = {executor.submit(_call_one, m): m for m in models}
        for future in as_completed(futures):
            model, result = future.result()
            outcomes[model] = result
            console.print(f"  [dim]✓ {model}[/dim]")

    return outcomes


# ── Session persistence ──────────────────────────────────────────────────────


def _safe_session_name(name: str) -> str:
    """Sanitize a session name to prevent path traversal."""
    sanitized = name.lstrip("/").replace("\\", "/").rstrip("/")
    parts = [p for p in sanitized.split("/") if p not in ("", ".", "..")]
    return "/".join(parts)


def save_session(
    name: str,
    question: str,
    result: dict,
    append: bool = False,
) -> Path:
    """Save a Q&A to a session file. Returns the file path."""
    safe_name = _safe_session_name(name)
    path = (SESSION_DIR / safe_name).resolve()
    if not str(path).startswith(str(SESSION_DIR.resolve())):
        raise ValueError(f"Invalid session name: {name}")
    path = path.with_suffix(".md")

    if not append or not path.exists():
        # New session header
        header = f"""# Research Session: {name}

**Date:** {datetime.now(tz=timezone.utc).isoformat()}
**Model:** {result.get('model', 'unknown')}
**Embedding model:** {result.get('embedding_model', DEFAULT_EMBED_MODEL)}
**K retrieved:** {result.get('k_retrieved', DEFAULT_K)}
**Threshold:** {result.get('threshold', DEFAULT_THRESHOLD)}

---

"""
        path.write_text(header, encoding="utf-8")
    else:
        header = ""

    # Q&A entry
    source_lines = []
    for i, s in enumerate(result.get("sources", []), 1):
        citekey = s.get("citekey", "")
        cite_str = f"@{citekey}" if citekey else f"source-{i}"
        title = s.get("title", "Unknown")
        year = s.get("year", "")
        year_str = f" ({year})" if year else ""
        source_lines.append(
            f"- [{i}] {cite_str} — \"{title}\"{year_str} "
            f"(relevance: {s.get('similarity', '?'):.2f})"
        )

    sources_block = (
        "\n".join(source_lines) if source_lines else "(No sources retrieved)"
    )

    entry = f"""
## Q: {question}

### Sources consulted
{sources_block}

### Answer
{result['answer']}

---
"""

    with path.open("a", encoding="utf-8") as f:
        if header:
            f.write(header)
        f.write(entry)

    return path


def _save_comparison_session(
    name: str, question: str, outcomes: dict[str, dict], append: bool = False
) -> Path:
    """Save a multi-model comparison to a session file."""
    safe_name = _safe_session_name(name)
    path = (SESSION_DIR / safe_name).resolve()
    if not str(path).startswith(str(SESSION_DIR.resolve())):
        raise ValueError(f"Invalid session name: {name}")
    path = path.with_suffix(".md")

    if not append or not path.exists():
        models_used = ", ".join(outcomes.keys())
        header = f"""# Comparison Session: {name}

**Date:** {datetime.now(tz=timezone.utc).isoformat()}
**Models compared:** {models_used}

---

"""
        path.write_text(header, encoding="utf-8")
    else:
        header = ""

    # Build sources from first model's result
    first = next(iter(outcomes.values()), {})
    source_lines = []
    for i, s in enumerate(first.get("sources", []), 1):
        citekey = s.get("citekey", "")
        cite_str = f"@{citekey}" if citekey else f"source-{i}"
        title = s.get("title", "Unknown")
        year = s.get("year", "")
        year_str = f" ({year})" if year else ""
        source_lines.append(f"- [{i}] {cite_str} — \"{title}\"{year_str}")

    sources_block = "\n".join(source_lines) if source_lines else "(No sources)"

    entry_parts = [f"## Q: {question}\n"]
    entry_parts.append("### Sources consulted")
    entry_parts.append(sources_block)
    entry_parts.append("")

    for model_name, r in outcomes.items():
        entry_parts.append(f"### {model_name} ({r.get('model', '?')})")
        entry_parts.append(f"**Tokens:** {r.get('input_tokens', '?')} in / {r.get('output_tokens', '?')} out")
        if r.get("cost"):
            entry_parts.append(f"**Cost:** ${r['cost']:.4f}")
        entry_parts.append("")
        entry_parts.append(r.get("answer", ""))
        entry_parts.append("")
        entry_parts.append("---")
        entry_parts.append("")

    entry = "\n".join(entry_parts)

    with path.open("a", encoding="utf-8") as f:
        if header:
            f.write(header)
        f.write(entry)

    return path


def list_sessions() -> list[dict]:
    """List all saved research sessions."""
    sessions = []
    for f in sorted(SESSION_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        name = f.stem
        q_count = text.count("## Q:")
        q_pos = text.rfind("## Q:")
        last_q = ""
        if q_pos >= 0:
            q_line_start = q_pos + len("## Q: ")
            q_line_end = text.find("\n", q_line_start)
            last_q = text[q_line_start:q_line_end].strip()[:80]

        sessions.append(
            {
                "name": name,
                "path": f,
                "questions": q_count,
                "last_question": last_q,
                "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
            }
        )
    return sessions


# ── CLI ──────────────────────────────────────────────────────────────────────


@click.group()
def main():
    """RAG research assistant for your Zotero PDF library."""


@main.command("index")
@click.option(
    "--collection", "-c", default=None, help="Restrict to Zotero collection (partial name match)."
)
@click.option("--limit", "-n", default=None, type=int, help="Max items to process.")
@click.option("--force", is_flag=True, help="Re-index even if already in store.")
@click.option(
    "--embedding-model",
    default=DEFAULT_EMBED_MODEL,
    help="Embedding model to use.",
)
@click.option(
    "--chunk-size",
    default=CHUNK_SIZE,
    type=int,
    help="Chunk size in characters.",
)
def index_cmd(collection, limit, force, embedding_model, chunk_size):
    """Index Zotero PDFs into the local vector store."""
    console.print("[bold]Researcher: Index[/bold]\n")

    stats = index_zotero_papers(
        collection_name=collection,
        limit=limit,
        force=force,
        embedding_model=embedding_model,
        chunk_size=chunk_size,
    )

    console.print("")
    table = Table(title="Index Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green")
    table.add_row("Total items in Zotero", str(stats["total_items"]))
    table.add_row("Items with PDFs", str(stats["with_pdfs"]))
    table.add_row("Indexed (new)", str(stats["indexed"]))
    table.add_row("Skipped (already indexed)", str(stats["skipped"]))
    table.add_row("Failed (no text / error)", str(stats["failed"]))
    table.add_row("Total chunks stored", str(stats["total_chunks"]))
    console.print(table)

    console.print(
        f"\n[dim]Embedding model: {embedding_model}[/dim]\n"
        f"[dim]Storage: {CHROMA_DIR}[/dim]"
    )


@main.command("ask")
@click.argument("question")
@click.option("--k", "-k", "k_chunks", default=DEFAULT_K, type=int, help="Chunks to retrieve.")
@click.option(
    "--threshold", "-t", default=DEFAULT_THRESHOLD, type=float, help="Similarity threshold (0–1)."
)
@click.option(
    "--model",
    "-m",
    default="claude",
    type=click.Choice(list(MODELS.keys())),
    help="LLM for answer generation.",
)
@click.option("--temperature", default=0.3, type=float, help="LLM temperature.")
@click.option("--save", "-o", default=None, help="Save Q&A to session file.")
@click.option(
    "--session", default=None, help="Append to existing session file (for follow-up questions)."
)
@click.option("--raw", is_flag=True, help="Print raw text instead of rendered markdown.")
@click.option(
    "--compare",
    default=None,
    help="Compare answers from multiple models. Comma-separated list, e.g. 'claude,gemini,gpt'.",
)
@click.option(
    "--embedding-model",
    default=DEFAULT_EMBED_MODEL,
    help="Embedding model (must match index).",
)
def ask_cmd(question, k_chunks, threshold, model, temperature, save, session, raw, compare, embedding_model):
    """Ask a research question against your indexed documents."""
    # Check index exists
    if not CHROMA_DIR.exists():
        console.print(
            "[red]No index found. Run 'researcher.py index' first.[/red]"
        )
        sys.exit(1)

    collection = _get_collection()

    # Check stale index
    index_meta = _get_index_meta(collection)
    if index_meta and index_meta.get("embedding_model") != embedding_model:
        console.print(
            f"[yellow]Warning: index was built with {index_meta['embedding_model']}, "
            f"querying with {embedding_model}. Results may be inaccurate.[/yellow]\n"
        )

    if compare:
        models = [m.strip() for m in compare.split(",") if m.strip() in MODELS]
        if not models:
            console.print(f"[red]No valid models in --compare list. Available: {', '.join(MODELS.keys())}[/red]")
            sys.exit(1)
        try:
            outcomes = compare_research_question(
                question=question,
                models=models,
                temperature=temperature,
                k=k_chunks,
                threshold=threshold,
                embedding_model=embedding_model,
                collection=collection,
            )
        except RuntimeError as e:
            console.print(f"[red]Comparison failed: {e}[/red]")
            sys.exit(1)

        table = Table(title=f"Comparison: {question[:60]}...", show_lines=True)
        table.add_column("Model", style="cyan", width=12)
        table.add_column("Answer", style="white", width=50)
        table.add_column("Tokens", style="dim", width=14)
        table.add_column("Cost", style="dim", width=8)

        for m in models:
            r = outcomes.get(m, {})
            table.add_row(
                m,
                (r.get("answer", "") or "")[:400],
                f"{r.get('input_tokens', '?')}/{r.get('output_tokens', '?')}",
                f"${r.get('cost', 0):.4f}" if r.get("cost") else "?",
            )
        console.print(table)

        # Save comparison session
        session_name = save or session
        if session_name:
            _save_comparison_session(session_name, question, outcomes, session is not None)
            console.print(f"\n[green]Comparison saved: {SESSION_DIR / f'{session_name}.md'}[/green]")
    else:
        try:
            result = ask_research_question(
                question=question,
                model=model,
                temperature=temperature,
                k=k_chunks,
                threshold=threshold,
                embedding_model=embedding_model,
                collection=collection,
            )
        except RuntimeError as e:
            console.print(f"[red]LLM call failed: {e}[/red]")
            sys.exit(1)

        console.print("[bold]Answer:[/bold]\n")
        if raw:
            click.echo(result["answer"])
        else:
            console.print(Markdown(result["answer"]))

        # Token/cost footer
        if result.get("input_tokens") or result.get("output_tokens"):
            console.print(
                f"\n[dim]tokens: {result.get('input_tokens', '?')} in, "
                f"{result.get('output_tokens', '?')} out[/dim]"
            )
            if result.get("cost"):
                console.print(f"[dim]cost: ~${result['cost']:.4f}[/dim]")

        # Save session
        session_name = save or session
        if session_name:
            path = save_session(
                name=session_name,
                question=question,
                result=result,
                append=bool(session),
            )
            console.print(f"\n[green]Session saved: {path}[/green]")


@main.command("sessions")
@click.option("--view", "-v", default=None, help="View a session (name or 'last').")
def sessions_cmd(view):
    """View or list past research sessions."""
    if view:
        if view == "last":
            sessions = list_sessions()
            if not sessions:
                console.print("[yellow]No sessions found.[/yellow]")
                return
            view = sessions[0]["name"]

        path = SESSION_DIR / f"{view}.md"
        if not path.exists():
            console.print(f"[red]Session '{view}' not found.[/red]")
            sys.exit(1)

        content = path.read_text(encoding="utf-8")
        console.print(Markdown(content))
    else:
        sessions = list_sessions()
        if not sessions:
            console.print("[yellow]No sessions found.[/yellow]")
            console.print(
                f"[dim]Sessions directory: {SESSION_DIR}[/dim]"
            )
            return

        table = Table(title="Research Sessions")
        table.add_column("Name", style="cyan")
        table.add_column("Questions", style="green")
        table.add_column("Last Question", style="white")
        for s in sessions:
            table.add_row(s["name"], str(s["questions"]), s["last_question"])
        console.print(table)
        console.print(
            f"\n[dim]View a session: ./researcher.py sessions --view <name>[/dim]"
        )


@main.command("stats")
def stats_cmd():
    """Show index statistics."""
    if not CHROMA_DIR.exists():
        console.print("[yellow]No index found. Run 'researcher.py index' first.[/yellow]")
        return

    collection = _get_collection()
    stats = _get_index_stats(collection)

    table = Table(title="Vector Index Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Documents indexed", str(stats["documents"]))
    table.add_row("Total chunks", str(stats["chunks"]))
    table.add_row("Collection name", COLLECTION_NAME)

    index_meta = stats.get("index_meta") or {}
    table.add_row("Embedding model", index_meta.get("embedding_model", "unknown"))
    table.add_row("Chunk size", str(index_meta.get("chunk_size", "?")))
    table.add_row("Chunk overlap", str(index_meta.get("chunk_overlap", "?")))
    table.add_row("Last indexed", index_meta.get("indexed_at", "unknown"))
    table.add_row("Storage path", str(CHROMA_DIR))

    console.print(table)


if __name__ == "__main__":
    main()
