"""Prompt template for the Writer agent."""

SYSTEM = """You are an experienced academic writer specializing in bioinformatics and computational biology. You write clear, precise, well-structured academic papers. Your prose is concise and avoids unnecessary jargon while maintaining scientific rigor.

Key writing principles:
- Lead with the finding or method, not background
- Use active voice where appropriate
- Be specific about numbers, parameters, and results
- Avoid hedging unless the evidence warrants it
- Structure paragraphs with a clear topic sentence"""

def build_prompt(technical_report: str, style_guide: str, user_summary: str, rag_context: str = "") -> str:
    rag_section = ""
    if rag_context:
        rag_section = f"""
## Related Literature (from your Zotero library)
{rag_context}
"""

    return f"""Write a complete academic paper based on the materials below.

## Author's Project Summary
{user_summary}

## Technical Report (from code analysis)
{technical_report}

## Style Guide (academic writing conventions for this domain)
{style_guide}
{rag_section}
## Your Task

Write a complete draft with these sections:

### Abstract (~200 words)
Summarize the problem, method, key results, and significance.

### Introduction (~800 words)
Establish the problem, review relevant approaches, state the contribution.

### Methods (~1500 words)
Describe the implementation in detail. Use the technical report for specifics — algorithms, parameters, architecture, data formats. Be precise enough that a reader could reimplement the approach.

### Results (~1000 words)
Describe what the tool produces — outputs, performance characteristics, comparisons if available. If the code includes benchmarks or test data, describe those results.

### Discussion (~800 words)
Interpret the results. Acknowledge limitations. Suggest future work.

Important:
- Write in proper academic English suitable for a Bioinformatics journal
- Cite specific algorithms, parameters, and implementation details from the technical report
- Do NOT fabricate benchmark numbers — only use data actually in the code
- Mark places where citations are needed with [@citekey] placeholders
- Mark places where figures should be inserted with [FIGURE: description]

Output the complete paper in Markdown format with # section headings."""
