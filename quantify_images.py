#!/usr/bin/env python3
"""macOS automation tool that runs ImageJ to measure images automatically."""

from __future__ import annotations

import csv
import shlex
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
DEFAULT_IMAGEJ_PATH = Path("/Applications/ImageJ.app/Contents/MacOS/ImageJ")


@dataclass
class ThresholdChoice:
    method: str  # "otsu" or "manual"
    manual_value: Optional[int] = None

    def describe(self) -> str:
        if self.method == "otsu":
            return "Otsu automatic threshold"
        return f"Manual threshold ({self.manual_value})"


def prompt_path(prompt: str, default: Optional[Path], must_exist: bool, expect_dir: bool) -> Path:
    while True:
        display = prompt
        if default is not None:
            display += f" [{default}]"
        display += ": "
        user_input = input(display).strip()
        if user_input == "":
            if default is None:
                print("Please provide a value.\n")
                continue
            candidate = default
        else:
            candidate = Path(user_input).expanduser()
        if must_exist:
            if expect_dir and not candidate.is_dir():
                print("The provided path is not an existing directory. Please try again.\n")
                continue
            if not expect_dir and not candidate.is_file():
                print("The provided path is not an existing file. Please try again.\n")
                continue
        return candidate.resolve()


def prompt_imagej_path() -> Path:
    print("Enter the full path to your ImageJ executable (inside ImageJ.app).")
    path = prompt_path("ImageJ path", DEFAULT_IMAGEJ_PATH if DEFAULT_IMAGEJ_PATH.exists() else None, True, False)
    return path


def prompt_image_folder() -> Path:
    print("\nProvide the folder that contains the images you want to process.")
    return prompt_path("Images folder", None, True, True)


def prompt_output_path(default_folder: Path) -> Path:
    suggested = default_folder / "measurements.csv"
    print("\nProvide the CSV file path where measurements should be saved.")
    path = prompt_path("Output CSV", suggested, False, False)
    if path.suffix.lower() != ".csv":
        print("The output will be saved as a CSV file. Appending .csv extension.")
        path = path.with_suffix(".csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def prompt_threshold() -> ThresholdChoice:
    print("\nChoose a thresholding method:")
    print("  1) Otsu automatic threshold")
    print("  2) Manual threshold value")
    while True:
        selection = input("Select 1 or 2: ").strip()
        if selection == "1":
            return ThresholdChoice(method="otsu")
        if selection == "2":
            while True:
                value = input("Enter manual threshold (0-255): ").strip()
                if not value.isdigit():
                    print("Please enter an integer between 0 and 255.")
                    continue
                manual_value = int(value)
                if 0 <= manual_value <= 255:
                    return ThresholdChoice(method="manual", manual_value=manual_value)
                print("Threshold must be between 0 and 255.")
        print("Invalid selection. Please choose 1 or 2.\n")


def build_macro_text(image_folder: Path, output_csv: Path, threshold: ThresholdChoice) -> str:
    folder = str(image_folder).replace("\\", "\\\\")
    output_path = str(output_csv).replace("\\", "\\\\")
    threshold_mode = threshold.method
    manual_value = threshold.manual_value if threshold.manual_value is not None else 0

    extensions_check = " or ".join(
        f"endsWith(lower, \"{ext}\")" for ext in sorted(SUPPORTED_EXTENSIONS)
    )

    manual_threshold_block = "\n" + textwrap.dedent(
        f"""
        else if (thresholdMode == \"manual\") {{
            setThreshold({manual_value}, 255);
            setOption(\"BlackBackground\", false);
            run(\"Convert to Mask\");
        }}
        """
    ).strip()

    macro = f"""
    folder = \"{folder if folder.endswith('/') else folder + '/'}\";
    outputPath = \"{output_path}\";
    thresholdMode = \"{threshold_mode}\";

    setBatchMode(true);
    run(\"Close All\");
    run(\"Clear Results\");
    run(\"Set Measurements...\", \"area mean standard min max display redirect=None decimal=3\");

    list = getFileList(folder);
    for (i = 0; i < list.length; i++) {{
        name = list[i];
        if (endsWith(name, \"/\"))
            continue;
        lower = toLowerCase(name);
        if (!({extensions_check}))
            continue;
        path = folder + name;
        open(path);
        run(\"8-bit\");
        if (thresholdMode == \"otsu\") {{
            setAutoThreshold(\"Otsu dark\");
            setOption(\"BlackBackground\", false);
            run(\"Convert to Mask\");
        }}{manual_threshold_block}
        run(\"32-bit\");
        run(\"Measure\");
        close();
    }}
    saveAs(\"Results\", outputPath);
    setBatchMode(false);
    """
    return textwrap.dedent(macro).strip() + "\n"


def format_command(command: list[str]) -> str:
    return " ".join(shlex.quote(token) for token in command)


def verify_results_csv(output_csv: Path) -> bool:
    if not output_csv.is_file():
        return False
    try:
        with output_csv.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            rows = list(reader)
    except Exception:
        return False
    if len(rows) < 2:
        return False
    # Ensure at least one measurement value exists (any numeric entry apart from header)
    for row in rows[1:]:
        if any(cell.strip() for cell in row[1:]):
            return True
    return False


def run_headless(imagej_path: Path, macro_path: Path) -> Optional[subprocess.CompletedProcess[str]]:
    command = [str(imagej_path), "--headless", "--macro", str(macro_path)]
    print("\nRunning ImageJ in headless mode...")
    print("Command:", format_command(command))
    try:
        result = subprocess.run(command, capture_output=True, text=True)
    except FileNotFoundError:
        print(f"ImageJ executable not found at {imagej_path}", file=sys.stderr)
        return None
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    return result


def run_applescript(imagej_path: Path, macro_path: Path, output_csv: Path, timeout: int = 600) -> bool:
    app_bundle = imagej_path
    # Try to locate the .app bundle if the binary path was supplied.
    if not app_bundle.name.endswith(".app"):
        for parent in imagej_path.parents:
            if parent.name.endswith(".app"):
                app_bundle = parent
                break
    script = textwrap.dedent(
        """
        on run argv
            set appBundle to POSIX file (item 1 of argv)
            set macroPath to item 2 of argv
            set outputPath to item 3 of argv

            tell application "Finder" to open appBundle
            delay 3

            tell application "System Events"
                repeat until exists process "ImageJ"
                    delay 0.5
                end repeat
                tell process "ImageJ"
                    tell menu bar 1
                        tell menu bar item "File"
                            tell menu "File"
                                click menu item "Run Macro..."
                            end tell
                        end tell
                    end tell
                end tell
            end tell

            delay 1
            tell application "System Events"
                keystroke macroPath
                key code 36 -- Return key
            end tell

            -- Wait until the results CSV appears with data
            set doneProcessing to false
            repeat while doneProcessing is false
                try
                    do shell script "test -s " & quoted form of outputPath
                    set doneProcessing to true
                on error
                    delay 1
                end try
            end repeat

            delay 1
            tell application "ImageJ" to quit
        end run
        """
    ).strip()

    with TemporaryDirectory() as tmp:
        script_path = Path(tmp) / "imagej_automation.scpt"
        script_path.write_text(script, encoding="utf-8")
        command = [
            "osascript",
            str(script_path),
            str(app_bundle),
            str(macro_path),
            str(output_csv),
        ]
        print("\nRunning ImageJ via AppleScript automation...")
        print("Command:", format_command(command))
        try:
            proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except FileNotFoundError:
            print("osascript is not available. Cannot run AppleScript fallback.", file=sys.stderr)
            return False

        start = time.time()
        while proc.poll() is None:
            if time.time() - start > timeout:
                proc.terminate()
                print("AppleScript automation timed out.", file=sys.stderr)
                return False
            time.sleep(1)

        stdout, stderr = proc.communicate()
        if stdout:
            print(stdout.strip())
        if stderr:
            print(stderr.strip(), file=sys.stderr)

    return verify_results_csv(output_csv)


def main() -> int:
    print("ImageJ Batch Measurement Tool")
    print("================================")

    imagej_path = prompt_imagej_path()
    image_folder = prompt_image_folder()
    output_csv = prompt_output_path(image_folder)
    threshold_choice = prompt_threshold()

    print("\nConfiguration summary:")
    print(f"  ImageJ: {imagej_path}")
    print(f"  Image folder: {image_folder}")
    print(f"  Output CSV: {output_csv}")
    print(f"  Threshold: {threshold_choice.describe()}")

    if output_csv.exists():
        output_csv.unlink()

    macro_text = build_macro_text(image_folder, output_csv, threshold_choice)

    with TemporaryDirectory() as tmp:
        macro_path = Path(tmp) / "batch_macro.ijm"
        macro_path.write_text(macro_text, encoding="utf-8")

        result = run_headless(imagej_path, macro_path)
        if result and result.returncode == 0 and verify_results_csv(output_csv):
            print("\nMeasurements captured successfully in headless mode.")
            return 0

        print(
            "\nHeadless execution did not produce a valid results file."
            " ImageJ may not support headless mode on your system."
        )
        print("Command executed:", format_command([str(imagej_path), "--headless", "--macro", str(macro_path)]))
        choice = input("Would you like to try the AppleScript automation fallback? [y/N]: ").strip().lower()
        if choice != "y":
            print("Exiting without running AppleScript automation.")
            return 1

        if run_applescript(imagej_path, macro_path, output_csv):
            print("\nMeasurements captured successfully via AppleScript automation.")
            return 0

        print("\nAppleScript automation failed to produce a valid results file.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
