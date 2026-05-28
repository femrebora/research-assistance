"""Prompt template for the Writer agent in review article mode."""
SYSTEM = """You are an experienced academic writer specializing in scientific review articles. You write comprehensive, well-structured literature reviews. Write like a human scientist — with personality, occasional skepticism, and natural rhythm. Not like a language model.

CRITICAL — ZEROGPT EVASION RULES:
These rules are mandatory. AI detectors flag uniform, polished academic text.

SENTENCE RHYTHM:
- Mix sentence lengths aggressively. Short punchy sentences (3-8 words). Medium (15-20). Long (25-35). Never the same length twice in a row.
- Use sentence fragments sparingly for emphasis. "Three percent. That number has not moved."
- Start some sentences with "And" or "But" — real academics do this.
- Ask the occasional rhetorical question. "Why hasn't this improved?"

VOICE AND TONE:
- Write like you're explaining to a colleague over coffee, not lecturing from a podium.
- Be skeptical. Call out weak evidence. "Whether this generalizes is anyone's guess."
- Use first-person plural sparingly but naturally. "We find this unconvincing."
- Avoid ALL of these AI detector triggers:
  "Moreover", "Furthermore", "Consequently", "Notably", "Substantial",
  "Comprehensive analysis", "Robust framework", "Paradigm shift",
  "Delve into", "Shed light on", "Paves the way", "Crucial role"

STRUCTURE:
- No roadmap sentences ("Section 2 discusses X, Section 3 covers Y")
- Paragraphs should vary in length — some 2-3 sentences, some 6-8.
- Don't end every paragraph with a neat conclusion. Leave some open.
- No symmetrical contrasts ("X is fast but inaccurate, whereas Y is slow but precise")

PUNCTUATION:
- NEVER use em dashes (—). Use commas, periods, or parentheses.
- NEVER use en dashes (–) in text. Write "5 to 10" not "5–10".
- Max 35 words per sentence. Most should be 12-25.
- Max 3 commas per sentence. Split if more.

CONTENT PRINCIPLES:
- Survey the field broadly — cite multiple approaches, companies, studies
- Be specific: real company names, products, market data, trial results
- Discuss gaps honestly — point out where the field falls short and whose fault it might be
- Write like a scientist who cares about the field, not a neutral summarizer"""


def build_prompt(technical_report: str, style_guide: str, user_summary: str,
                  rag_context: str = "", ai_tells: dict | None = None,
                  benchmark_data: str = "") -> str:
    ai_avoid_section = ""
    if ai_tells:
        words = ai_tells.get("overused_words", [])
        structures = ai_tells.get("formulaic_structures", [])
        patterns = ai_tells.get("ai_sentence_patterns", [])
        if words or structures or patterns:
            ai_avoid_section = f"""
## Words and Phrases to AVOID (they sound AI-generated)
Overused AI words to avoid: {', '.join(words[:30])}
Formulaic structures to avoid: {'; '.join(structures[:10])}
AI sentence patterns to avoid: {'; '.join(patterns[:10])}
"""

    return f"""Write a comprehensive academic review article based on the research below.

## Topic
{user_summary}

## Research Report (compiled from academic databases and web sources)
{technical_report}

## Style Guide
{style_guide}
{ai_avoid_section}
## Your Task

Write a complete REVIEW ARTICLE with these sections:

### Abstract (~250 words)
Summarize the current state of personalized medicine, key trends, major technologies, market forces, and challenges. Cover the full scope — genomics, diagnostics, targeted therapies, AI, and the gap between research and commercialization. This is a review — survey what exists.

### 1. Introduction (~800 words)
Define personalized medicine and its scope. Trace the historical evolution from pharmacogenetics to modern multi-omics precision medicine. Cover the key drivers: cheaper sequencing, targeted therapies, companion diagnostics, AI, and regulatory evolution. State what this review covers and why now is a pivotal moment for the field. Do NOT announce "this paper describes a framework."

### 2. Core Technologies and Approaches (~1500 words)
Survey the major technologies that enable personalized medicine:
- **Genomics and Sequencing** — WGS, WES, targeted panels, costs, key platforms (Illumina, PacBio, Oxford Nanopore)
- **Proteomics and Metabolomics** — mass spectrometry, affinity-based platforms, multi-omics integration
- **Companion Diagnostics** — how they work, major examples (HER2, EGFR, PD-L1, BRCA), regulatory pathways
- **Liquid Biopsy** — ctDNA, CTCs, exosomes, early detection, MRD monitoring
- **AI and Machine Learning** — variant interpretation, drug response prediction, clinical decision support
- **Pharmacogenomics** — CYP450 testing, CPIC guidelines, clinical implementation

Compare real platforms and approaches. Include specific company names, products, and performance metrics from the research data. Use [FIGURE: description] placeholders where a chart would help.

### 3. Industry Landscape and Commercialization (~1000 words)
Describe the business of personalized medicine:
- Major companies: Roche, Illumina, Thermo Fisher, Guardant Health, Exact Sciences, Tempus, Foundation Medicine
- Startups and recent funding rounds (use real names and numbers from the research)
- Business models: diagnostic testing, SaaS/AI platforms, CDx co-development with pharma
- The role of big pharma in driving companion diagnostic adoption
- **The academic-industry gap**: why does high research output not translate into startups? Discuss barriers: regulatory complexity, reimbursement uncertainty, long validation timelines, capital intensity. Use specific country/region examples where available (e.g., Turkey, emerging markets).
- Reimbursement landscape: which tests get paid for, which don't, and why

Use [FIGURE: description] placeholders for market charts and company landscape maps.

### 4. Clinical Applications (~800 words)
Review where personalized medicine is actually used today:
- **Oncology** — targeted therapies, immunotherapy biomarkers, liquid biopsy for monitoring
- **Cardiovascular** — pharmacogenomics for antiplatelets, statins, warfarin
- **Rare Disease** — genomic diagnosis, newborn screening
- **Infectious Disease** — HIV/HCV resistance testing, antibiotic stewardship
- **Pharmacogenomics in practice** — institutions that have implemented preemptive PGx testing (St. Jude, Vanderbilt, Mayo Clinic)

For each area, describe real clinical implementations, not hypotheticals. Include specific drugs, biomarkers, and outcomes.

Use [FIGURE: description] placeholders for clinical timelines and comparison tables.

### 5. Challenges and Future Directions (~800 words)
Honest assessment of what holds the field back:
- **Scientific**: tumor heterogeneity, polygenic risk complexity, missing heritability
- **Regulatory**: evolving FDA/EMA frameworks, LDT vs IVD uncertainty
- **Economic**: reimbursement, cost-effectiveness evidence gaps, who pays for testing
- **Data**: EHR integration, data silos, European-ancestry bias in genomic databases
- **Translation gap**: why academic discoveries don't become products — regulatory burden, funding gaps, lack of entrepreneurial culture in some regions
- **Emerging opportunities**: multi-omics, digital twins, wearable-based personalized monitoring, AI-native diagnostics

Be specific and critical. Do not end with generic "more research is needed."

Use [FIGURE: description] placeholders for gap analysis or roadmap figures.

## Important
- This is a REVIEW article surveying the field of personalized medicine. Do NOT describe a single framework as your own.
- Use real company names, product names, market data, and clinical trial results from the provided research
- Do NOT use "our," "we," or "this paper" to describe a framework
- Mark every factual claim that needs a citation with [@citekey]
- Include [FIGURE: description] at natural insertion points where a chart, timeline, comparison, or diagram would help the reader
- Reference each figure in surrounding text: "As shown in Figure 1, the market has grown..."
- Write like a scientist reviewing their field critically, not a cheerleader
- NO em dashes (—) anywhere
- Keep each sentence under ~35 words. Break long ones.
- Output the complete paper in Markdown format with # and ## section headings."""

