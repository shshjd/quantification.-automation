#!/usr/bin/env python3
"""Batch image quantification utility.

This script replicates the behaviour of the original Fiji macro by reading a
list of image paths, converting each image to 32-bit grayscale, computing basic
measurements (area and integrated density), and writing the results to a CSV
file.  It can be executed on any platform with Python 3.9+ and the required
libraries installed.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable, List, Sequence

import numpy as np
from PIL import Image, ImageOps


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Quantify a batch of images by computing area and integrated density "
            "after converting to 32-bit grayscale."
        )
    )
    parser.add_argument(
        "list_file",
        type=Path,
        help=(
            "Plain-text file containing one image path per line. Relative paths "
            "are resolved from the location of the list file."
        ),
    )
    parser.add_argument(
        "output_csv",
        type=Path,
        help="Destination CSV file for measurement results.",
    )
    parser.add_argument(
        "--decimal-places",
        type=int,
        default=3,
        metavar="N",
        help="Number of decimal places to include in the output (default: 3).",
    )
    return parser.parse_args(argv)


def read_image_paths(list_file: Path) -> Iterable[Path]:
    if not list_file.exists():
        raise FileNotFoundError(f"List file not found: {list_file}")

    base_dir = list_file.parent
    with list_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            path = raw_line.strip()
            if not path:
                continue
            candidate = Path(path)
            if not candidate.is_absolute():
                candidate = (base_dir / candidate).resolve()
            yield candidate


def quantify_image(image_path: Path) -> tuple[float, float]:
    try:
        with Image.open(image_path) as image:
            # Convert to grayscale and ensure 32-bit floating point precision.
            grayscale = ImageOps.grayscale(image)
            grayscale_array = np.array(grayscale, dtype=np.float32)
    except OSError as exc:
        raise RuntimeError(f"Failed to open {image_path}: {exc}") from exc

    area = float(grayscale_array.shape[0] * grayscale_array.shape[1])
    integrated_density = float(grayscale_array.sum())
    return area, integrated_density


def write_results(
    rows: Iterable[tuple[str, float, float]],
    output_csv: Path,
    decimal_places: int,
) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["Image", "Area", "IntDen"]

    fmt = f"{{:.{decimal_places}f}}"

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for image_name, area, intden in rows:
            writer.writerow(
                {
                    "Image": image_name,
                    "Area": fmt.format(area),
                    "IntDen": fmt.format(intden),
                }
            )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    try:
        image_paths = list(read_image_paths(args.list_file))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(exc, file=sys.stderr)
        return 1

    if not image_paths:
        print("The provided list file does not contain any image paths.", file=sys.stderr)
        return 1

    results: List[tuple[str, float, float]] = []
    skipped: List[str] = []

    for image_path in image_paths:
        if not image_path.exists():
            skipped.append(str(image_path))
            continue

        try:
            area, integrated_density = quantify_image(image_path)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            skipped.append(f"{image_path} (error: {exc})")
            continue

        results.append((str(image_path), area, integrated_density))

    if not results:
        print("No images were processed successfully.", file=sys.stderr)
        for entry in skipped:
            print(f"Skipped: {entry}", file=sys.stderr)
        return 1

    try:
        write_results(results, args.output_csv, args.decimal_places)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"Failed to write output CSV: {exc}", file=sys.stderr)
        return 1

    print(f"Saved results to: {args.output_csv}")

    if skipped:
        print("The following images were skipped:", file=sys.stderr)
        for entry in skipped:
            print(f"  {entry}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
