"""Prompt template for the Academic Style Researcher agent."""

SYSTEM = """You analyze academic writing in a specific field and extract the characteristic patterns that make papers in that field sound authentic. You study: common transition phrases, sentence structures, section conventions, vocabulary choices, and rhetorical moves."""

def build_prompt(domain: str) -> str:
    return f"""Analyze the writing style of academic papers in {domain}.

Based on your knowledge of top-tier {domain} papers, produce a style guide covering:

## 1. Common Sentence Structures
What sentence patterns appear frequently? (e.g., "We [verb] [noun] using [method] to [purpose]")

## 2. Transition Phrases
What transitions do authors use between sections and paragraphs?

## 3. Section Conventions
How is each section typically structured? What information goes where?

## 4. Vocabulary
What domain-specific terminology is standard? What verbs are commonly used to describe methods and results?

## 5. Rhetorical Moves
How do authors establish significance, acknowledge limitations, and position their work?

## 6. Citation Patterns
How are citations integrated? (e.g., parenthetical, narrative, footnote-style)

Write in a format that can be used as a writing guide. Be specific — include actual example phrases and structures."""
