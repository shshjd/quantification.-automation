#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

default_input="${SCRIPT_DIR}/input_images"
default_results="${SCRIPT_DIR}/results"
default_logs="${SCRIPT_DIR}/run_logs"

input_dir="$(prompt_directory "Enter the input images directory" "${default_input}")"
output_dir="$(prompt_directory "Enter the results directory" "${default_results}")"
log_dir="$(prompt_directory "Enter the run logs directory" "${default_logs}")"

echo "Using input directory:   ${input_dir}"
echo "Using results directory: ${output_dir}"
echo "Using run logs directory: ${log_dir}"

image_listing="$(python3 - <<'PY' "${input_dir}"
import os, sys
from pathlib import Path

SUPPORTED = {'.tif', '.tiff', '.png', '.jpg', '.jpeg', '.bmp', '.gif'}

root = Path(sys.argv[1])
if not root.is_dir():
    sys.exit(0)

files = [entry.name for entry in root.iterdir()
         if entry.is_file() and entry.suffix.lower() in SUPPORTED]
files.sort()

print(f"COUNT:{len(files)}")
for name in files:
    print(f"FILE:{name}")
PY
)"

image_count=0
image_files=()
while IFS= read -r line; do
  case "$line" in
    COUNT:*) image_count="${line#COUNT:}" ;;
    FILE:*) image_files+=("${line#FILE:}") ;;
  esac
done <<<"${image_listing}"

if (( image_count == 0 )); then
  echo "Error: No supported image files were found in '${input_dir}'." >&2
  echo "Supported extensions: tif, tiff, png, jpg, jpeg, bmp, gif." >&2
  exit 1
fi

echo "Found ${image_count} image(s) to process:"
for image in "${image_files[@]}"; do
  echo "  - ${image}"
done

macro_path="${SCRIPT_DIR}/macros/mean_intensity.ijm"

if [[ ! -f "${macro_path}" ]]; then
  echo "Error: Macro file not found at '${macro_path}'." >&2
  exit 1
fi

args="input=${input_dir},output=${output_dir},log=${log_dir}"

echo "Starting ImageJ in headless mode..."
"${IMAGEJ_APP}" --headless -macro "${macro_path}" "${args}"

log_file="${log_dir%/}/run.log"
if [[ -f "${log_file}" ]]; then
  printf '\nLast 10 log entries:\n'
  tail -n 10 "${log_file}"
fi

printf '\nDone. Review %s for the results CSV and %s for the full log.\n' "${output_dir}" "${log_file}"
