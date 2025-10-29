#!/usr/bin/env python3
"""Command line tool for automating a headless Fiji-based image quantification workflow on macOS."""

from __future__ import annotations

import csv
import json
import math
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, stdev
from tempfile import TemporaryDirectory
from typing import Dict, List, Optional, Sequence, Tuple

try:
    from openpyxl import Workbook
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit("openpyxl is required to run this program. Please install it before continuing.") from exc

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
REQUIRED_LAUNCHER_SUFFIX = ("Fiji.app", "Contents", "MacOS", "ImageJ-macosx")

# Default paths tailored for the primary workflow environment. Adjust these values to
# match your own system or leave them as ``None`` to disable the auto-filled prompts.
DEFAULT_IMAGES_FOLDER: Optional[Path] = Path("/Users/oleksandrgorelik/Desktop/RAW")
DEFAULT_FIJI_LAUNCHER: Optional[Path] = Path("/Applications/ImageJ.app/Contents/MacOS/ImageJ")
DEFAULT_OUTPUT_DIRECTORY: Optional[Path] = Path("/Users/oleksandrgorelik/Desktop/Quantification data")


@dataclass(frozen=True)
class Measurement:
    """Description of a measurement captured from the ImageJ results table."""

    key: str
    display_name: str
    imagej_option: str
    result_column: str


MEASUREMENTS: Tuple[Measurement, ...] = (
    Measurement(key="area", display_name="Area", imagej_option="area", result_column="Area"),
    Measurement(key="mean", display_name="Mean", imagej_option="mean", result_column="Mean"),
    Measurement(key="std_dev", display_name="StdDev", imagej_option="standard", result_column="StdDev"),
    Measurement(key="min", display_name="Min", imagej_option="min", result_column="Min"),
    Measurement(key="max", display_name="Max", imagej_option="max", result_column="Max"),
    Measurement(key="int_den", display_name="IntDen", imagej_option="integrated", result_column="IntDen"),
)


def build_measurement_option_string(measurement_defs: Sequence[Measurement]) -> str:
    """Build the option string passed to ImageJ's Set Measurements command."""

    options: List[str] = []
    seen = set()
    for measurement in measurement_defs:
        if measurement.imagej_option not in seen:
            options.append(measurement.imagej_option)
            seen.add(measurement.imagej_option)
    options.extend(["limit", "display", "redirect=None", "decimal=3"])
    return " ".join(options)


MEASUREMENT_OPTION_STRING = build_measurement_option_string(MEASUREMENTS)


@dataclass(frozen=True)
class ThresholdConfig:
    """Configuration for thresholding operations."""

    method: str
    manual_value: Optional[int] = None

    @property
    def description(self) -> str:
        if self.method == "otsu":
            return "Otsu automatic threshold"
        return f"Manual threshold at {self.manual_value}"

    @property
    def macro_manual_value(self) -> int:
        return int(self.manual_value or 0)


@dataclass(frozen=True)
class RunConfiguration:
    """Aggregate of user-selected configuration."""

    image_folder: Path
    fiji_launcher: Path
    threshold: ThresholdConfig
    output_excel: Path



def format_command(command: Sequence[str]) -> str:
    """Return a shell-escaped representation of a command."""

    return " ".join(shlex.quote(token) for token in command)


def ensure_trailing_separator(path: Path) -> str:
    """Return the path as a string with a trailing separator for ImageJ."""

    text = str(path)
    if not text.endswith("/"):
        text += "/"
    return text


def prompt_for_images_folder(default_folder: Optional[Path] = None) -> Path:
    """Prompt the user for the folder that contains images to process."""

    while True:
        prompt = "Images folder"
        if default_folder is not None:
            prompt += f" [{default_folder}]"
        prompt += ": "

        user_input = input(prompt).strip()
        if not user_input and default_folder is None:
            print("An images folder is required. Please provide a valid directory.\n")
            continue
        folder = default_folder if not user_input else Path(user_input).expanduser()
        if folder.is_dir():
            return folder.resolve()
        print("The specified folder does not exist or is not a directory. Please try again.\n")


def prompt_for_fiji_launcher(default_launcher: Optional[Path] = None) -> Path:
    """Prompt for the Fiji launcher path and validate that it is macOS-compatible."""

    print("\nFiji launcher path must end with Fiji.app/Contents/MacOS/ImageJ-macosx.")

    while True:
        prompt = "Fiji launcher path"
        if default_launcher is not None:
            prompt += f" [{default_launcher}]"
        prompt += ": "

        user_input = input(prompt).strip()
        if not user_input and default_launcher is None:
            print(
                "The Fiji launcher path is required. Provide the full path ending with "
                "Fiji.app/Contents/MacOS/ImageJ-macosx.\n"
            )
            continue
        candidate = default_launcher if not user_input else Path(user_input).expanduser()
        if candidate.name == "JavaApplicationStub":
            print(
                "The JavaApplicationStub launcher is not supported. Use "
                ".../Fiji.app/Contents/MacOS/ImageJ-macosx instead.\n"
            )
            continue
        if candidate.is_dir() and candidate.name.lower().endswith(".app"):
            print(
                "Please point directly to the launcher inside the app bundle: "
                ".../Fiji.app/Contents/MacOS/ImageJ-macosx.\n"
            )
            continue
        if not candidate.exists():
            print("The specified path does not exist. Please try again.\n")
            continue
        resolved = candidate.resolve()
        if not resolved.is_file():
            print("The provided path is not a file. Please choose the ImageJ-macosx launcher.\n")
            continue
        if len(resolved.parts) < len(REQUIRED_LAUNCHER_SUFFIX) or tuple(resolved.parts[-4:]) != REQUIRED_LAUNCHER_SUFFIX:
            print(
                "Invalid Fiji launcher. It must end with Fiji.app/Contents/MacOS/ImageJ-macosx on macOS.\n"
            )
            continue
        if not os.access(resolved, os.X_OK):
            print(
                "The specified launcher is not executable. Check the file permissions or reinstall Fiji.\n"
            )
            continue
        if probe_fiji_headless(resolved):
            return resolved
        print("Headless probe failed. Please choose a different Fiji launcher.\n")


def probe_fiji_headless(executable: Path) -> bool:
    """Verify that the Fiji launcher can run headlessly."""

    command = [str(executable), "--ij2", "--headless", "--help"]
    print(f"\nChecking Fiji headless support: {format_command(command)}")

    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as exc:
        stdout = (exc.stdout or "").strip()
        stderr = (exc.stderr or "").strip()
        if stdout:
            print("Probe output:\n" + stdout)
        if stderr:
            print("Probe error output:\n" + stderr, file=sys.stderr)
        print(
            "Fiji failed the headless probe. Ensure the launcher is correct and that Fiji supports headless mode."
        )
        return False
    except FileNotFoundError:
        print("The Fiji launcher could not be executed. Please verify the path and try again.")
        return False

    print("Headless probe succeeded.")
    return True


def prompt_threshold_method() -> ThresholdConfig:
    """Prompt the user to choose between Otsu and manual thresholding."""

    print("\nThreshold methods:")
    print("  otsu   - Automatically determine a threshold using Fiji's Otsu implementation.")
    print("  manual - Provide a fixed threshold between 0 and 255.")

    while True:
        method = input("Choose threshold method [otsu]: ").strip().lower() or "otsu"
        if method == "otsu":
            return ThresholdConfig(method="otsu")
        if method == "manual":
            while True:
                value_raw = input("Enter manual threshold value (0-255): ").strip()
                try:
                    value = int(value_raw)
                except ValueError:
                    print("Please provide a whole number between 0 and 255.\n")
                    continue
                if 0 <= value <= 255:
                    return ThresholdConfig(method="manual", manual_value=value)
                print("Value must be between 0 and 255.\n")
        else:
            print("Invalid choice. Please enter 'otsu' or 'manual'.\n")


def prompt_output_path(default_path: Path) -> Path:
    """Prompt the user for an output Excel file path."""

    print("\nProvide a destination for the Excel report. Leave blank to use the default path.")
    print(f"Default: {default_path}")

    while True:
        user_input = input(f"Excel output path [{default_path}]: ").strip()
        if not user_input:
            return default_path
        path = Path(user_input).expanduser()
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
        return path.resolve()


def gather_configuration() -> RunConfiguration:
    """Collect all required inputs from the user before running the workflow."""

    print("Image Quantification Automation (Fiji Headless Edition)\n" + "=" * 58)
    images_folder = prompt_for_images_folder(DEFAULT_IMAGES_FOLDER)
    fiji_launcher = prompt_for_fiji_launcher(DEFAULT_FIJI_LAUNCHER)
    threshold_config = prompt_threshold_method()

    if DEFAULT_OUTPUT_DIRECTORY is not None:
        default_output = DEFAULT_OUTPUT_DIRECTORY / "quantification_measurements.xlsx"
    else:
        default_output = images_folder / "quantification_measurements.xlsx"
    output_path = prompt_output_path(default_output)

    print("\nConfiguration Summary:")
    print(f"  Images folder:  {images_folder}")
    print(f"  Fiji launcher:  {fiji_launcher}")
    print(f"  Threshold:      {threshold_config.description}")
    print(f"  Output Excel:   {output_path}")

    confirm = input("\nProceed with these settings? [y/N]: ").strip().lower()
    if confirm != "y":
        raise SystemExit("Operation cancelled by user.")

    return RunConfiguration(
        image_folder=images_folder,
        fiji_launcher=fiji_launcher,
        threshold=threshold_config,
        output_excel=output_path,
    )


@dataclass
class FijiRunResult:
    """Container for Fiji execution output."""

    command: Sequence[str]
    stdout: str
    stderr: str


def build_macro_content(
    input_dir: Path,
    results_csv: Path,
    threshold_config: ThresholdConfig,
    measurement_defs: Sequence[Measurement],
) -> str:
    """Generate the ImageJ macro that performs the batch quantification."""

    extension_list = ";".join(sorted(ext.lower() for ext in SUPPORTED_EXTENSIONS))
    macro = f"""// Auto-generated macro created by quantify_images.py
inputDir = {json.dumps(ensure_trailing_separator(input_dir))};
resultsPath = {json.dumps(str(results_csv))};
thresholdMethod = {json.dumps(threshold_config.method)};
manualValue = {threshold_config.macro_manual_value};
extensionList = {json.dumps(extension_list)};
measurementOptions = {json.dumps(MEASUREMENT_OPTION_STRING)};

run(\"Set Measurements...\", measurementOptions);
setBatchMode(true);
run(\"Clear Results\");

fileList = getFileList(inputDir);
processed = 0;
for (i = 0; i < fileList.length; i++) {{
    name = fileList[i];
    if (endsWith(name, \"/\"))
        continue;
    if (!shouldProcess(name, extensionList))
        continue;
    path = inputDir + name;
    print(\"Processing: \" + path);
    open(path);
    run(\"8-bit\");
    thresholdLabel = \"-\";
    if (thresholdMethod == \"otsu\") {{
        setAutoThreshold(\"Otsu\");
        getThreshold(lower, upper);
        thresholdLabel = \"Otsu (\" + d2s(lower, 2) + \")\";
    }} else {{
        lower = manualValue;
        if (lower < 0) lower = 0;
        if (lower > 255) lower = 255;
        setThreshold(lower, 255);
        thresholdLabel = \"Manual (\" + lower + \")\";
    }}
    run(\"32-bit\");
    run(\"Measure\");
    rowIndex = nResults - 1;
    setResult(\"Image\", rowIndex, name);
    setResult(\"Threshold Applied\", rowIndex, thresholdLabel);
    updateResults();
    close();
    processed++;
}}

saveAs(\"Results\", resultsPath);
run(\"Clear Results\");
setBatchMode(false);
print(\"Processed \" + processed + \" image(s).\");
print(\"Results saved to \" + resultsPath);

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


def run_fiji_macro(imagej_executable: Path, macro_path: Path, results_csv: Path) -> FijiRunResult:
    """Invoke Fiji headlessly to execute the generated macro."""

    command = [str(imagej_executable), "--ij2", "--headless", "--console", "--macro", str(macro_path)]
    print(f"\nRunning Fiji command: {format_command(command)}")

    try:
        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stdout_text = (exc.stdout or "").strip()
        stderr_text = (exc.stderr or "").strip()
        if stdout_text:
            print("Fiji stdout:\n" + stdout_text)
        if stderr_text:
            print("Fiji stderr:\n" + stderr_text, file=sys.stderr)
        raise SystemExit(
            "Fiji exited with an error while executing the macro.\n"
            f"Command used: {format_command(command)}\n"
            "Please review the output above, resolve the issue, and try again."
        ) from exc
    except FileNotFoundError as exc:
        raise SystemExit(f"Fiji launcher not found: {imagej_executable}") from exc

    stdout_text = completed.stdout.strip()
    stderr_text = completed.stderr.strip()
    if not results_csv.exists() or results_csv.stat().st_size == 0:
        if stdout_text:
            print("Fiji stdout:\n" + stdout_text)
        if stderr_text:
            print("Fiji stderr:\n" + stderr_text, file=sys.stderr)
        raise SystemExit(
            "Fiji completed without producing a results CSV.\n"
            f"Command used: {format_command(command)}\n"
            "Please inspect the Fiji output above and confirm that the macro finished in headless mode."
        )

    if stdout_text:
        print("Fiji stdout:\n" + stdout_text)
    if stderr_text:
        print("Fiji stderr:\n" + stderr_text, file=sys.stderr)

    return FijiRunResult(command=command, stdout=stdout_text, stderr=stderr_text)


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
    """Load measurement results produced by Fiji."""

    image_names: List[str] = []
    thresholds: List[str] = []
    measurements: List[Dict[str, float]] = []

    with results_csv.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit(
                "The results CSV produced by Fiji is missing headers. Please rerun the workflow or update Fiji."
            )
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


def process_images(config: RunConfiguration) -> Tuple[List[Dict[str, float]], List[str], List[str]]:
    """Process the images with Fiji and return measurement data."""

    image_files = find_images(config.image_folder)
    if not image_files:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise SystemExit(
            "No supported image files were found in the selected folder. "
            f"Add images with extensions {supported} and try again."
        )

    measurement_defs = list(MEASUREMENTS)

    with TemporaryDirectory() as tempdir:
        temp_dir = Path(tempdir)
        macro_path = temp_dir / "batch_quantify.ijm"
        results_csv = temp_dir / "imagej_results.csv"

        macro_content = build_macro_content(config.image_folder, results_csv, config.threshold, measurement_defs)
        macro_path.write_text(macro_content, encoding="utf-8")

        run_fiji_macro(config.fiji_launcher, macro_path, results_csv)

        image_names, thresholds, measurement_results = parse_results_csv(results_csv, measurement_defs)

    if not image_names:
        raise SystemExit(
            "The results CSV produced by Fiji did not contain any measurements. "
            "Ensure the images can be processed headlessly and try again."
        )

    return measurement_results, image_names, thresholds


def _excel_value(value: float) -> Optional[float]:
    """Return a value that is safe to store in Excel (convert NaN to None)."""

    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def export_to_excel(
    results: Sequence[Dict[str, float]],
    image_names: Sequence[str],
    thresholds: Sequence[str],
    config: RunConfiguration,
    measurement_defs: Sequence[Measurement],
) -> None:
    """Write measurement results to an Excel workbook with a summary sheet."""

    workbook = Workbook()
    measurements_sheet = workbook.active
    measurements_sheet.title = "Measurements"

    headers = ["Image", "Threshold Applied"] + [measurement.display_name for measurement in measurement_defs]
    measurements_sheet.append(headers)

    for name, threshold_value, measurement in zip(image_names, thresholds, results):
        row = [name, threshold_value]
        for measurement_def in measurement_defs:
            row.append(_excel_value(measurement.get(measurement_def.display_name, float("nan"))))
        measurements_sheet.append(row)

    summary_sheet = workbook.create_sheet("Summary")
    summary_sheet.append(["Parameter", "Value"])
    summary_sheet.append(["Images folder", str(config.image_folder)])
    summary_sheet.append(["Fiji launcher", str(config.fiji_launcher)])
    summary_sheet.append(["Threshold method", config.threshold.description])
    if config.threshold.method == "manual":
        summary_sheet.append(["Manual threshold", config.threshold.manual_value])
    summary_sheet.append(["Images processed", len(image_names)])

    summary_sheet.append([])
    summary_sheet.append(["Measurement", "Mean", "StdDev", "Count"])

    for measurement_def in measurement_defs:
        values = [result.get(measurement_def.display_name, float("nan")) for result in results]
        clean_values = [value for value in values if not (isinstance(value, float) and math.isnan(value))]
        if clean_values:
            mean_value = mean(clean_values)
            stdev_value = stdev(clean_values) if len(clean_values) > 1 else float("nan")
        else:
            mean_value = float("nan")
            stdev_value = float("nan")
        summary_sheet.append(
            [
                measurement_def.display_name,
                _excel_value(mean_value),
                _excel_value(stdev_value),
                len(clean_values),
            ]
        )

    summary_sheet.append([])
    summary_sheet.append(["Image", "Threshold Applied"])
    for name, threshold_value in zip(image_names, thresholds):
        summary_sheet.append([name, threshold_value])

    try:
        workbook.save(config.output_excel)
    except Exception as exc:  # pragma: no cover - filesystem guard
        raise SystemExit(
            f"Failed to write Excel report: {exc}. Please verify the destination path and try again."
        ) from exc


def main() -> None:
    try:
        config = gather_configuration()
        results, image_names, thresholds = process_images(config)
        export_to_excel(results, image_names, thresholds, config, MEASUREMENTS)
    except KeyboardInterrupt:  # pragma: no cover - interactive guard
        print("\nOperation cancelled by user.")
        sys.exit(1)
    else:
        print("\nProcessing complete! Measurements exported to:")
        print(config.output_excel)


if __name__ == "__main__":
    main()
