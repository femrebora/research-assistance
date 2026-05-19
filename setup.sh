#!/usr/bin/env bash
# One-command setup for thesis-tools.
# Run from inside the thesis-tools directory.

set -e

echo "→ Creating Python virtualenv at ~/.venvs/thesis"
python3 -m venv ~/.venvs/thesis

echo "→ Activating and installing dependencies"
# shellcheck disable=SC1090
source ~/.venvs/thesis/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "→ Making scripts executable"
chmod +x ./*.py

if [ ! -f .env ]; then
    echo "→ Creating .env from template (you must edit it with your keys)"
    cp env.example .env
fi

echo ""
echo "Done. Next steps:"
echo "  1. Edit .env with your API keys and paths"
echo "  2. source ~/.venvs/thesis/bin/activate"
echo "  3. Test with: ./ask.py 'hello' --model claude"
