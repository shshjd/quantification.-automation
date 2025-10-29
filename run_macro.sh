#!/usr/bin/env bash
set -euo pipefail

prompt_directory() {
  local prompt_text="$1"
  local default_value="${2-}"
  local response
  while true; do
    if [[ -n "$default_value" ]]; then
      read -r -p "$prompt_text [$default_value]: " response || true
      response="${response:-$default_value}"
    else
      read -r -p "$prompt_text: " response || true
    fi
    response="${response//\~/$(printf '%s' "$HOME")}" # expand leading ~
    if [[ -z "$response" ]]; then
      echo "Please provide a directory path." >&2
      continue
    fi
    response="$(python3 - <<'PY'
import os, sys
path = sys.stdin.read().strip()
print(os.path.abspath(os.path.expanduser(path)))
PY
<<<"$response")"
    if [[ -d "$response" ]]; then
      echo "$response"
      return 0
    fi
    read -r -p "Directory does not exist. Create it? [y/N]: " create || true
    case "$create" in
      [yY][eE][sS]|[yY])
        mkdir -p "$response"
        echo "$response"
        return 0
        ;;
      *)
        echo "Let's try again." >&2
        ;;
    esac
  done
}

if [[ -z "${IMAGEJ_APP:-}" ]]; then
  IMAGEJ_APP="/Applications/ImageJ/ImageJ.app/Contents/MacOS/ImageJ"
fi

if [[ ! -x "${IMAGEJ_APP}" ]]; then
  echo "Error: IMAGEJ executable not found at '${IMAGEJ_APP}'." >&2
  echo "Set the IMAGEJ_APP environment variable to your ImageJ binary path." >&2
  exit 1
fi

input_dir="$(prompt_directory "Enter the input images directory" "${PWD}/input_images")"
output_dir="$(prompt_directory "Enter the results directory" "${PWD}/results")"
log_dir="$(prompt_directory "Enter the run logs directory" "${PWD}/run_logs")"

macro_path="$(python3 - <<'PY'
import os
print(os.path.abspath(os.path.join(os.path.dirname(__file__), 'macros', 'mean_intensity.ijm')))
PY
)"

args="input=${input_dir},output=${output_dir},log=${log_dir}"

"${IMAGEJ_APP}" --headless -macro "${macro_path}" "${args}"
