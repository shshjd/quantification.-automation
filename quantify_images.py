#!/usr/bin/env python3
"""Command line tool for automating an image quantification workflow on macOS."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit("numpy is required to run this program. Please install it before continuing.") from exc

try:
    from openpyxl import Workbook
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit("openpyxl is required to run this program. Please install it before continuing.") from exc

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit("Pillow is required to run this program. Please install it before continuing.") from exc

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}

MeasurementFunc = Callable[[np.ndarray, Optional[np.ndarray]], float]


def _masked_values(data: np.ndarray, mask: Optional[np.ndarray]) -> np.ndarray:
    """Return pixels included in the mask (or the full image when mask is None)."""

    if mask is None:
        return data
    return data[mask]


def _mean_intensity(data: np.ndarray, mask: Optional[np.ndarray]) -> float:
    values = _masked_values(data, mask)
    if values.size == 0:
        return float("nan")
    return float(values.mean())


def _std_intensity(data: np.ndarray, mask: Optional[np.ndarray]) -> float:
    values = _masked_values(data, mask)
    if values.size == 0:
        return float("nan")
    return float(values.std(ddof=0))


def _min_intensity(data: np.ndarray, mask: Optional[np.ndarray]) -> float:
    values = _masked_values(data, mask)
    if values.size == 0:
        return float("nan")
    return float(values.min())


def _max_intensity(data: np.ndarray, mask: Optional[np.ndarray]) -> float:
    values = _masked_values(data, mask)
    if values.size == 0:
        return float("nan")
    return float(values.max())


def _sum_intensity(data: np.ndarray, mask: Optional[np.ndarray]) -> float:
    values = _masked_values(data, mask)
    if values.size == 0:
        return 0.0
    return float(values.sum())


def _foreground_area(data: np.ndarray, mask: Optional[np.ndarray]) -> float:
    if mask is None:
        return float(data.size)
    return float(mask.sum())


class Measurement:
    """Representation of a measurement that can be applied to an image array."""

    def __init__(self, name: str, description: str, func: MeasurementFunc) -> None:
        self.name = name
        self.description = description
        self.func = func

    def compute(self, image_data: np.ndarray, mask: Optional[np.ndarray]) -> float:
        return float(self.func(image_data, mask))


MEASUREMENTS: Dict[str, Measurement] = {
    "mean_intensity": Measurement(
        name="Mean Intensity",
        description="Average value of all pixels (or masked region) in 32-bit space.",
        func=_mean_intensity,
    ),
    "std_dev": Measurement(
        name="Standard Deviation",
        description="Standard deviation of pixel intensities.",
        func=_std_intensity,
    ),
    "min_intensity": Measurement(
        name="Minimum Intensity",
        description="Minimum pixel value.",
        func=_min_intensity,
    ),
    "max_intensity": Measurement(
        name="Maximum Intensity",
        description="Maximum pixel value.",
        func=_max_intensity,
    ),
    "sum_intensity": Measurement(
        name="Integrated Intensity",
        description="Sum of all pixel intensities.",
        func=_sum_intensity,
    ),
    "foreground_area": Measurement(
        name="Foreground Area (px)",
        description="Number of pixels classified as foreground by the threshold.",
        func=_foreground_area,
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
    print("  otsu    - Automatically determine a threshold using Otsu's method.")
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


def threshold_otsu(gray_array: np.ndarray) -> int:
    """Compute Otsu's threshold for a grayscale image."""

    histogram, _ = np.histogram(gray_array.ravel(), bins=256, range=(0, 256))
    total = histogram.sum()
    if total == 0:
        return 0

    sum_total = np.dot(np.arange(256), histogram)
    sum_background = 0.0
    weight_background = 0.0
    max_variance = -1.0
    threshold = 0

    for level in range(256):
        weight_background += histogram[level]
        if weight_background == 0:
            continue
        weight_foreground = total - weight_background
        if weight_foreground == 0:
            break
        sum_background += level * histogram[level]
        mean_background = sum_background / weight_background
        mean_foreground = (sum_total - sum_background) / weight_foreground
        between_var = weight_background * weight_foreground * (mean_background - mean_foreground) ** 2
        if between_var > max_variance:
            max_variance = between_var
            threshold = level
    return threshold


def apply_threshold(image: Image.Image, config: ThresholdConfig) -> Tuple[Image.Image, Optional[np.ndarray], Optional[int]]:
    """Apply thresholding based on the user's configuration."""

    gray = image.convert("L")
    gray_array = np.array(gray, dtype=np.uint8)

    if config.method == "none":
        return gray, None, None

    if config.method == "otsu":
        threshold_value = threshold_otsu(gray_array)
    else:
        threshold_value = config.value if config.value is not None else 0

    mask = gray_array >= threshold_value
    binary_array = np.where(mask, 255, 0).astype(np.uint8)
    return Image.fromarray(binary_array, mode="L"), mask, int(threshold_value)


def convert_to_float32(image: Image.Image) -> np.ndarray:
    """Convert a PIL image to a 32-bit floating point numpy array."""

    array = np.array(image, dtype=np.float32)
    return array


def gather_configuration() -> Tuple[Path, ThresholdConfig, List[str], Path]:
    """Collect all required inputs from the user before running the workflow."""

    print("Image Quantification Automation\n" + "=" * 34)
    image_folder = prompt_for_directory("Enter the folder containing your images: ")

    threshold_config = prompt_threshold_method()
    measurement_keys = prompt_measurements()

    default_output = image_folder / "quantification_measurements.xlsx"
    output_path = prompt_output_path(default_output)

    print("\nConfiguration Summary:")
    print(f"  Image folder:      {image_folder}")
    print(f"  Threshold method:  {threshold_config}")
    print(f"  Measurements:      {', '.join(measurement_keys)}")
    print(f"  Output file:       {output_path}")

    confirm = input("\nProceed with processing? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Operation cancelled by user.")
        raise SystemExit(0)

    return image_folder, threshold_config, measurement_keys, output_path


def find_images(folder: Path) -> List[Path]:
    """Return a sorted list of image files within the folder."""

    return sorted(
        [path for path in folder.iterdir() if path.suffix.lower() in SUPPORTED_EXTENSIONS and path.is_file()]
    )


def compute_measurements(image_data: np.ndarray, mask: Optional[np.ndarray], measurement_keys: Sequence[str]) -> Dict[str, float]:
    """Compute the requested measurements for an image."""

    results: Dict[str, float] = {}
    for key in measurement_keys:
        measurement = MEASUREMENTS[key]
        try:
            value = measurement.compute(image_data, mask)
        except ValueError:
            value = float("nan")
        results[measurement.name] = value
    return results


def export_to_excel(results: Sequence[Dict[str, float]], image_names: Sequence[str], output_path: Path, *, threshold_details: Sequence[Optional[int]]) -> None:
    """Write measurement results to an Excel workbook."""

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Measurements"

    measurement_names: List[str] = []
    if results:
        measurement_names = list(results[0].keys())

    headers = ["Image", "Threshold Applied"] + measurement_names
    sheet.append(headers)

    for name, threshold_value, measurement in zip(image_names, threshold_details, results):
        row = [name, threshold_value if threshold_value is not None else "-"]
        row.extend(measurement.get(metric, float("nan")) for metric in measurement_names)
        sheet.append(row)

    workbook.save(output_path)


def process_images(folder: Path, threshold_config: ThresholdConfig, measurement_keys: Sequence[str]) -> Tuple[List[Dict[str, float]], List[str], List[Optional[int]]]:
    """Process each image in the folder and return measurements and metadata."""

    image_files = find_images(folder)
    if not image_files:
        print("No supported image files were found in the selected folder.")
        raise SystemExit(1)

    measurement_results: List[Dict[str, float]] = []
    image_names: List[str] = []
    thresholds_used: List[Optional[int]] = []

    for image_path in image_files:
        print(f"Processing {image_path.name} ...")
        with Image.open(image_path) as original_image:
            processed_image, mask, threshold_value = apply_threshold(original_image, threshold_config)
            float_data = convert_to_float32(processed_image)
            measurements = compute_measurements(float_data, mask, measurement_keys)

        measurement_results.append(measurements)
        image_names.append(image_path.name)
        thresholds_used.append(threshold_value)

    return measurement_results, image_names, thresholds_used


def main() -> None:
    try:
        folder, threshold_config, measurement_keys, output_path = gather_configuration()
        results, image_names, thresholds_used = process_images(folder, threshold_config, measurement_keys)
        export_to_excel(results, image_names, output_path, threshold_details=thresholds_used)
    except KeyboardInterrupt:  # pragma: no cover - interactive guard
        print("\nOperation cancelled by user.")
        sys.exit(1)
    else:
        print("\nProcessing complete! Measurements exported to:")
        print(output_path)


if __name__ == "__main__":
    main()
