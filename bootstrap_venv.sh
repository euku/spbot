#!/bin/bash
# Create the venv for the SpBot scripts. Must run inside the job image, e.g.:
#   toolforge jobs run bootstrap-venv-standalone --image python3.11 --wait \
#     --command "cd ~/src && ./bootstrap_venv.sh"
# Refuses to touch an existing venv; remove or rename it yourself first.
set -euo pipefail

VENV="${VENV:-$HOME/pyvenv-standalone}"
if [ -e "$VENV" ]; then
    echo "$VENV already exists, not touching it" >&2
    exit 1
fi

python3 -m venv "$VENV"
"$VENV/bin/pip" install -U pip wheel
"$VENV/bin/pip" install -r "$(dirname "$0")/requirements.txt"
"$VENV/bin/pip" freeze
