#!/bin/sh
# Open the chant browser and service planner (Linux/macOS). Make it double-clickable with: chmod +x psalter.sh
# The Python packages go in a folder of their own here (.venv), since newer systems won't let pip
# install into the system's Python.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "Setting up the Python packages (once)…"
  python3 -m venv .venv || { echo "Could not make .venv: on Debian or Ubuntu, install python3-venv first (sudo apt install python3-venv)."; exit 1; }
fi
for r in requirements.txt parish/plugins/*/requirements.txt; do
  [ -f "$r" ] && { .venv/bin/python -m pip install -q --disable-pip-version-check -r "$r" || echo "Could not install the packages in $r (see above)."; }
done
exec .venv/bin/python tools/serve.py
