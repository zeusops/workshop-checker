#!/bin/bash

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
name=$(basename "$0")
script_name=${name%.sh}.py
cd "$DIR" || exit 1
"$DIR/venv/bin/python" "$script_name" "$@"
