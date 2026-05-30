#!/usr/bin/env bash
# One command setup for research assistant.
# Run from inside the research assistant directory.

set -e

VENV="${RA_VENV:-$HOME/.venvs/thesis}"
THESIS_ROOT_DEFAULT="$HOME/thesis"
ZOTERO_STORAGE_DEFAULT="$HOME/Zotero/storage"

echo "Creating Python virtualenv at $VENV"
python3 -m venv "$VENV"

echo "Activating virtualenv and installing the package in editable mode"
# shellcheck disable=SC1090
source "$VENV/bin/activate"

python -m pip install --upgrade pip
python -m pip install -e ".[dev,desktop]"

if [ ! -f .env ]; then
    echo "Creating .env from env.example"
    cp env.example .env

    echo "Updating default local paths in .env"
    python - <<PY
from pathlib import Path

env_path = Path(".env")
text = env_path.read_text()

home = str(Path.home())

text = text.replace("# THESIS_ROOT=~/thesis", f"THESIS_ROOT={home}/thesis")
text = text.replace("# ZOTERO_STORAGE=~/Zotero/storage", f"ZOTERO_STORAGE={home}/Zotero/storage")
text = text.replace("THESIS_ROOT=/home/emre/thesis", f"THESIS_ROOT={home}/thesis")
text = text.replace("ZOTERO_STORAGE=/home/emre/Zotero/storage", f"ZOTERO_STORAGE={home}/Zotero/storage")
text = text.replace("THESIS_ROOT=~/thesis", f"THESIS_ROOT={home}/thesis")
text = text.replace("ZOTERO_STORAGE=~/Zotero/storage", f"ZOTERO_STORAGE={home}/Zotero/storage")

env_path.write_text(text)
PY
fi

echo "Creating default research folders"
mkdir -p "$THESIS_ROOT_DEFAULT/logs"
mkdir -p "$ZOTERO_STORAGE_DEFAULT"

echo ""
echo "Done. Next steps:"
echo "  1. Edit .env with your API keys"
echo "  2. source $VENV/bin/activate"
echo "  3. Test CLI: ra-ask 'hello' --model claude"
echo "  4. Index PDFs: ra-researcher index"
echo "  5. Web UI: ra-web"
echo "  6. Desktop app: ra-desktop"
echo ""
echo "Open the Web UI at http://127.0.0.1:5050"
