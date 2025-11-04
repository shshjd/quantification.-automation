#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <fiji_executable> <list_file> <output_results_file>" >&2
  exit 1
}

if [ "$#" -ne 3 ]; then
  usage
fi

FIJI_EXEC="$1"
LIST_FILE="$2"
OUTPUT_FILE="$3"

if [ ! -x "$FIJI_EXEC" ]; then
  echo "Error: Fiji executable '$FIJI_EXEC' not found or not executable." >&2
  exit 1
fi

if [ ! -f "$LIST_FILE" ]; then
  echo "Error: List file '$LIST_FILE' not found." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MACRO_PATH="$REPO_ROOT/macros/batch_area_measurement.ijm"

if [ ! -f "$MACRO_PATH" ]; then
  echo "Error: Macro file '$MACRO_PATH' not found." >&2
  exit 1
fi

"$FIJI_EXEC" --headless -macro "$MACRO_PATH" "list=$LIST_FILE output=$OUTPUT_FILE"
