#!/usr/bin/env python3
"""Command line tool for automating an ImageJ-based image quantification workflow on macOS."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List, Optional, Sequence, Tuple

try:
    from openpyxl import Workbook
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit("openpyxl is required to run this program. Please install it before continuing.") from exc

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


@dataclass(frozen=True)
class Measurement:
    """Description of a measurement available in ImageJ."""

    key: str
    display_name: str
    description: str
    imagej_option: str
    result_column: str


MEASUREMENTS: Dict[str, Measurement] = {
    "mean_intensity": Measurement(
        key="mean_intensity",
        display_name="Mean Intensity",
        description="Average pixel intensity (ImageJ \"Mean\").",
        imagej_option="mean",
        result_column="Mean",
    ),
    "std_dev": Measurement(
        key="std_dev",
        display_name="Standard Deviation",
        description="Standard deviation of pixel intensities (ImageJ \"StdDev\").",
        imagej_option="standard",
        result_column="StdDev",
    ),
    "min_intensity": Measurement(
        key="min_intensity",
        display_name="Minimum Intensity",
        description="Minimum pixel value (ImageJ \"Min\").",
        imagej_option="min",
        result_column="Min",
    ),
    "max_intensity": Measurement(
        key="max_intensity",
        display_name="Maximum Intensity",
        description="Maximum pixel value (ImageJ \"Max\").",
        imagej_option="max",
        result_column="Max",
    ),
    "sum_intensity": Measurement(
        key="sum_intensity",
        display_name="Integrated Density",
        description="Integrated density (ImageJ \"IntDen\").",
        imagej_option="integrated",
        result_column="IntDen",
    ),
    "foreground_area": Measurement(
        key="foreground_area",
        display_name="Foreground Area (px)",
        description="Pixel area of the measured region (ImageJ \"Area\").",
        imagej_option="area",
        result_column="Area",
    ),
}


class ThresholdConfig:
    """Configuration for thresholding operations."""

    def __init__(self, method: str, value: Optional[int] = None) -> None:
        self.method = method
        self.value = value

    def __str__(self) -> str:  # pragma: no cover - trivial
        if self.method == "none":
            return "No threshold (grayscale only)"
        if self.method == "manual":
            return f"Manual threshold at {self.value}"
        return self.method.capitalize()


def prompt_for_imagej_executable() -> Path:
    """Prompt the user for the ImageJ (or Fiji) executable path."""

    print("Provide the path to your ImageJ or Fiji installation (e.g. /Applications/Fiji.app).")
    print("You can paste the .app bundle or the executable inside Contents/MacOS.\n")

    while True:
        user_input = input("ImageJ application path: ").strip()
        if not user_input:
            print("An ImageJ path is required. Please try again.\n")
            continue
        candidate = Path(user_input).expanduser().resolve()
        executable = resolve_imagej_executable(candidate)
        if executable is None:
            print("Unable to locate the ImageJ executable at that path. Please try again.\n")
            continue
        if not os.access(executable, os.X_OK):
            print("The resolved ImageJ executable is not runnable. Please choose another path.\n")
            continue
        return executable


def resolve_imagej_executable(path: Path) -> Optional[Path]:
    """Resolve the actual executable inside an ImageJ/Fiji installation."""

    if path.is_file():
        return path

    if path.is_dir():
        candidates = [
            path / "Contents" / "MacOS" / "ImageJ-macosx",
            path / "Contents" / "MacOS" / "ImageJ",
            path / "Contents" / "MacOS" / "JavaApplicationStub",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate

    return None


def prompt_for_directory(prompt: str) -> Path:
    """Prompt the user for a directory path until a valid one is provided."""

    while True:
        user_input = input(prompt).strip()
        if not user_input:
            print("A folder path is required. Please try again.\n")
            continue
        folder = Path(user_input).expanduser().resolve()
        if folder.is_dir():
            return folder
        print("The path provided is not a directory. Please try again.\n")


def prompt_threshold_method() -> ThresholdConfig:
    """Collect threshold configuration from the user."""

    print("\nThreshold methods available:")
    print("  none    - Keep images in grayscale only.")
    print("  otsu    - Automatically determine a threshold using ImageJ's Otsu implementation.")
    print("  manual  - Specify a fixed threshold between 0 and 255.")

    while True:
        method = input("Choose threshold method [otsu]: ").strip().lower() or "otsu"
        if method not in {"none", "otsu", "manual"}:
            print("Invalid choice. Please enter 'none', 'otsu', or 'manual'.\n")
            continue
        if method == "manual":
            while True:
                value_raw = input("Enter manual threshold value (0-255): ").strip()
                try:
                    value = int(value_raw)
                except ValueError:
                    print("Please provide a valid integer between 0 and 255.\n")
                    continue
                if 0 <= value <= 255:
                    return ThresholdConfig(method="manual", value=value)
                print("Value must be between 0 and 255.\n")
        return ThresholdConfig(method=method)


def prompt_measurements() -> List[str]:
    """Prompt the user to choose which measurements to compute."""

    print("\nAvailable measurements (enter comma-separated keys):")
    for key, measurement in MEASUREMENTS.items():
        print(f"  {key:<15} - {measurement.description}")

    default_selection = ["mean_intensity", "std_dev", "sum_intensity", "foreground_area"]
    print("Default selection:", ", ".join(default_selection))

    while True:
        user_input = input("Measurements to compute [default]: ").strip()
        if not user_input:
            return default_selection
        selection = [item.strip().lower() for item in user_input.split(",") if item.strip()]
        unknown = [item for item in selection if item not in MEASUREMENTS]
        if unknown:
            print(f"Unrecognized measurement keys: {', '.join(unknown)}. Please try again.\n")
            continue
        if not selection:
            print("At least one measurement must be selected.\n")
            continue
        return selection


def prompt_output_path(default_path: Path) -> Path:
    """Prompt the user for an output Excel file path."""

    print("\nProvide a destination for the Excel report. Leave blank to use the default path.")
    print(f"Default: {default_path}")

    while True:
        user_input = input("Excel output path: ").strip()
        if not user_input:
            return default_path
        path = Path(user_input).expanduser().resolve()
        if path.is_dir():
            path = path / default_path.name
        if path.suffix.lower() != ".xlsx":
            print("The output file must have a .xlsx extension.\n")
            continue
        if not path.parent.exists():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:  # pragma: no cover - filesystem guard
                print(f"Unable to create directories for the output file: {exc}\n")
                continue
        return path


def gather_configuration() -> Tuple[Path, Path, ThresholdConfig, List[str], Path]:
    """Collect all required inputs from the user before running the workflow."""

    print("Image Quantification Automation (ImageJ Edition)\n" + "=" * 48)
    imagej_executable = prompt_for_imagej_executable()
    image_folder = prompt_for_directory("Enter the folder containing your images: ")

    threshold_config = prompt_threshold_method()
    measurement_keys = prompt_measurements()

    default_output = image_folder / "quantification_measurements.xlsx"
    output_path = prompt_output_path(default_output)

    print("\nConfiguration Summary:")
    print(f"  ImageJ executable: {imagej_executable}")
    print(f"  Image folder:      {image_folder}")
    print(f"  Threshold method:  {threshold_config}")
    print(f"  Measurements:      {', '.join(measurement_keys)}")
    print(f"  Output file:       {output_path}")

    confirm = input("\nProceed with processing? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Operation cancelled by user.")
        raise SystemExit(0)

    return imagej_executable, image_folder, threshold_config, measurement_keys, output_path


def ensure_trailing_separator(path: Path) -> str:
    """Return the path as a string with a trailing separator for ImageJ."""

    text = str(path)
    if not text.endswith("/"):
        text += "/"
    return text


def build_measurement_option_string(measurement_defs: Sequence[Measurement]) -> str:
    """Build the option string passed to ImageJ's Set Measurements command."""

    tokens: List[str] = []
    seen = set()
    for measurement in measurement_defs:
        option = measurement.imagej_option
        if option not in seen:
            tokens.append(option)
            seen.add(option)
    tokens.extend(["display", "redirect=None", "decimal=3"])
    return " ".join(tokens)


def build_macro_content(
    input_dir: Path,
    results_csv: Path,
    threshold_config: ThresholdConfig,
    measurement_defs: Sequence[Measurement],
) -> str:
    """Generate the ImageJ macro that performs the batch quantification."""

    measurement_options = build_measurement_option_string(measurement_defs)
    extension_list = ";".join(sorted(ext.lower() for ext in SUPPORTED_EXTENSIONS))
    manual_value = threshold_config.value if threshold_config.value is not None else 0

    macro = f"""// Auto-generated macro created by quantify_images.py
inputDir = {json.dumps(ensure_trailing_separator(input_dir))};
outputFile = {json.dumps(str(results_csv))};
thresholdMethod = {json.dumps(threshold_config.method)};
manualValue = {manual_value};
extensionList = {json.dumps(extension_list)};
measurementOptions = {json.dumps(measurement_options)};

run(\"Set Measurements...\", measurementOptions);
setBatchMode(true);
run(\"Clear Results\");

list = getFileList(inputDir);
for (i = 0; i < list.length; i++) {{
    name = list[i];
    if (endsWith(name, \"/\"))
        continue;
    if (!shouldProcess(name, extensionList))
        continue;
    path = inputDir + name;
    open(path);
    run(\"8-bit\");
    setOption(\"BlackBackground\", false);
    thresholdLabel = \"-\";
    if (thresholdMethod == \"otsu\") {{
        setAutoThreshold(\"Otsu\");
        setOption(\"Limit to threshold\", true);
        getThreshold(lower, upper);
        thresholdLabel = \"\" + lower;
    }} else if (thresholdMethod == \"manual\") {{
        lower = manualValue;
        if (lower < 0)
            lower = 0;
        if (lower > 255)
            lower = 255;
        setThreshold(lower, 255);
        setOption(\"Limit to threshold\", true);
        thresholdLabel = \"\" + lower;
    }} else {{
        resetThreshold();
        setOption(\"Limit to threshold\", false);
    }}
    run(\"32-bit\");
    run(\"Measure\");
    row = nResults - 1;
    setResult(\"Image\", row, name);
    setResult(\"Threshold Applied\", row, thresholdLabel);
    updateResults();
    close();
}}

saveAs(\"Results\", outputFile);
run(\"Clear Results\");
setBatchMode(false);

function shouldProcess(name, extensionList) {{
    lower = toLowerCase(name);
    exts = split(extensionList, \";\");
    for (j = 0; j < exts.length; j++) {{
        ext = exts[j];
        if (ext == \"\")
            continue;
        if (endsWith(lower, ext))
            return true;
    }}
    return false;
}}
"""
    return macro


def run_imagej_macro(imagej_executable: Path, macro_path: Path) -> None:
    """Invoke ImageJ headlessly to execute the generated macro."""

    command = [
        str(imagej_executable),
        "--ij2",
        "--headless",
        "--console",
        "-macro",
        str(macro_path),
    ]
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:  # pragma: no cover - runtime guard
        raise SystemExit(f"ImageJ executable not found: {imagej_executable}") from exc
    except subprocess.CalledProcessError as exc:  # pragma: no cover - runtime guard
        raise SystemExit("ImageJ reported an error while processing the images.") from exc


def find_images(folder: Path) -> List[Path]:
    """Return a sorted list of supported image files within the folder."""

    return sorted(
        [path for path in folder.iterdir() if path.suffix.lower() in SUPPORTED_EXTENSIONS and path.is_file()]
    )


def safe_float(value: Optional[str]) -> float:
    """Convert a string to float, returning NaN when conversion fails."""

    if value is None or value == "":
        return float("nan")
    try:
        return float(value)
    except ValueError:
        return float("nan")


def parse_results_csv(results_csv: Path, measurement_defs: Sequence[Measurement]) -> Tuple[List[str], List[str], List[Dict[str, float]]]:
    """Load measurement results produced by ImageJ."""

    image_names: List[str] = []
    thresholds: List[str] = []
    measurements: List[Dict[str, float]] = []

    with results_csv.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            image_name = row.get("Image") or row.get("Label") or ""
            threshold_value = row.get("Threshold Applied", "-")
            measurement_row: Dict[str, float] = {}
            for measurement in measurement_defs:
                measurement_row[measurement.display_name] = safe_float(row.get(measurement.result_column))
            image_names.append(image_name)
            thresholds.append(threshold_value if threshold_value else "-")
            measurements.append(measurement_row)

    return image_names, thresholds, measurements


def process_images(
    imagej_executable: Path,
    folder: Path,
    threshold_config: ThresholdConfig,
    measurement_keys: Sequence[str],
) -> Tuple[List[Dict[str, float]], List[str], List[str]]:
    """Process the images with ImageJ and return measurement data."""

    image_files = find_images(folder)
    if not image_files:
        print("No supported image files were found in the selected folder.")
        raise SystemExit(1)

    measurement_defs = [MEASUREMENTS[key] for key in measurement_keys]

    with TemporaryDirectory() as tempdir:
        temp_dir = Path(tempdir)
        macro_path = temp_dir / "batch_quantify.ijm"
        results_csv = temp_dir / "imagej_results.csv"

        macro_content = build_macro_content(folder, results_csv, threshold_config, measurement_defs)
        macro_path.write_text(macro_content, encoding="utf-8")

        run_imagej_macro(imagej_executable, macro_path)

        if not results_csv.exists():
            raise SystemExit("ImageJ did not produce a results file. Please check the console output for details.")

        image_names, thresholds, measurement_results = parse_results_csv(results_csv, measurement_defs)

    if not image_names:
        print("ImageJ did not return any measurement results.")
        raise SystemExit(1)

    return measurement_results, image_names, thresholds


def export_to_excel(
    results: Sequence[Dict[str, float]],
    image_names: Sequence[str],
    thresholds: Sequence[str],
    output_path: Path,
    measurement_keys: Sequence[str],
) -> None:
    """Write measurement results to an Excel workbook."""

    measurement_defs = [MEASUREMENTS[key] for key in measurement_keys]

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Measurements"

    headers = ["Image", "Threshold Applied"] + [measurement.display_name for measurement in measurement_defs]
    sheet.append(headers)

    for name, threshold_value, measurement in zip(image_names, thresholds, results):
        row = [name, threshold_value]
        for measurement_def in measurement_defs:
            row.append(measurement.get(measurement_def.display_name, float("nan")))
        sheet.append(row)

    workbook.save(output_path)


def main() -> None:
    try:
        imagej_executable, folder, threshold_config, measurement_keys, output_path = gather_configuration()
        results, image_names, thresholds = process_images(
            imagej_executable, folder, threshold_config, measurement_keys
        )
        export_to_excel(results, image_names, thresholds, output_path, measurement_keys)
    except KeyboardInterrupt:  # pragma: no cover - interactive guard
        print("\nOperation cancelled by user.")
        sys.exit(1)
    else:
        print("\nProcessing complete! Measurements exported to:")
        print(output_path)


if __name__ == "__main__":
    main()
