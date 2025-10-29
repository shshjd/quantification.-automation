#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}"
MACRO_PATH="${PROJECT_ROOT}/macros/mean_intensity.ijm"
INPUT_DIR="${PROJECT_ROOT}/input_images"
OUTPUT_DIR="${PROJECT_ROOT}/results"
LOG_DIR="${PROJECT_ROOT}/run_logs"

if [[ -z "${IMAGEJ_APP:-}" ]]; then
  IMAGEJ_APP="/Applications/ImageJ/ImageJ.app/Contents/MacOS/ImageJ"
fi

if [[ ! -x "${IMAGEJ_APP}" ]]; then
  echo "Error: IMAGEJ executable not found at '${IMAGEJ_APP}'." >&2
  echo "Set the IMAGEJ_APP environment variable to your ImageJ binary path." >&2
  exit 1
fi

mkdir -p "${INPUT_DIR}" "${OUTPUT_DIR}" "${LOG_DIR}"

ARGS="input=${INPUT_DIR},output=${OUTPUT_DIR},log=${LOG_DIR}"

"${IMAGEJ_APP}" --headless -macro "${MACRO_PATH}" "${ARGS}"
