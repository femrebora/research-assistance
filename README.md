# Thesis Tools

A small set of CLI scripts for thesis writing. Each script does one thing.
You decide when to run which. 

## What's here

- `ask.py` — ask any question to any model (Claude, Gemini, DeepSeek, GPT, local)
- `zot.py` — search your Zotero library from terminal
- `evidence.py` — query your PDFs via PaperQA2, save cited output
- `ideas.py` — get paragraph angles given evidence + a job statement
- `critique.py` — get critique of a draft paragraph you've written
- `verify.py` — check that all `[@citekey]` placeholders in a draft exist in your bibliography

## Setup (one time)

```bash
# Clean Python env (don't break your bioinformatics stack)
python -m venv ~/.venvs/thesis
source ~/.venvs/thesis/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy the env template and fill in your API keys
cp .env.example .env
# Edit .env with your keys

# Make scripts executable
chmod +x *.py
```

Add to your `~/.bashrc`:

```bash
alias thesis="source ~/.venvs/thesis/bin/activate && cd ~/thesis"
export $(cat ~/thesis/tools/.env | xargs)
```

## Daily use

```bash
# Search your Zotero library
./zot.py "NUMT contamination"

# Get evidence from your PDFs (PaperQA2)
./evidence.py "What are the main approaches to filtering NUMT in clinical mtDNA?" \
  --save evidence/ch1/numt_filtering.md

# Get paragraph angles
./ideas.py evidence/ch1/numt_filtering.md \
  --job "Establish NUMT contamination as a clinically significant problem"

# Ask any quick question, pick the model
./ask.py "Explain MitoScape's coverage-based filtering in one paragraph" --model claude
./ask.py "Same question" --model gemini   # second opinion
./ask.py "Same question" --model deepseek # cheaper option

# After you've written a paragraph in Google Docs, paste it back to critique
./critique.py --draft drafts/ch1_para_3.md \
  --job "Establish NUMT contamination as a clinically significant problem"

# Before submission, verify all citations resolve
./verify.py drafts/ch1_full.md --bib ~/thesis/bib/thesis.bib
```

## Logging

Every model call gets logged to `~/thesis/logs/YYYY-MM-DD.jsonl`.
One line per call: timestamp, model, prompt, response, cost.


