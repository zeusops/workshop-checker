#!/bin/bash

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
name=$(basename "$0")
script_name=${name%.sh}.py
cd "$DIR" || exit
"$DIR/.venv/bin/python" "src/workshop_checker/$script_name" "$@"
