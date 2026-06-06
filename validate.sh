#!/usr/bin/env sh
set -eu

PYTHON_BIN="${PYTHON:-python3}"

"$PYTHON_BIN" scripts/validate-firmware-contract.py
"$PYTHON_BIN" -m unittest discover -s tests -v
