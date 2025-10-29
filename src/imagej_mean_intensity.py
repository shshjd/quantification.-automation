"""Batch ImageJ mean intensity measurement helper."""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent

import pandas as pd

DEFAULT_EXTENSIONS = (
    ".tif",
    ".tiff",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
)


class ImageJError(RuntimeError):
    """Raised when ImageJ fails to produce measurement data."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run ImageJ in headless mode to compute the mean pixel intensity for "
            "all images in a directory and write the results to an Excel file."
        )
    )
    parser.add_argument(
        "input_dir",
        type=Path,
        help="Directory that contains the images to measure.",
    )
    parser.add_argument(
        "output_excel",
        type=Path,
        help="Destination Excel file that will receive the measurement table.",
    )
    parser.add_argument(
        "--imagej",
        dest="imagej_path",
        type=Path,
        default=None,
        help=(
            "Path to the ImageJ or Fiji executable. Defaults to the IMAGEJ_PATH "
            "environment variable when available."
        ),
    )
    parser.add_argument(
        "--extensions",
        nargs="*",
        default=DEFAULT_EXTENSIONS,
        metavar="EXT",
        help=(
            "File extensions (with dots) to include. Matching is case-insensitive. "
            "The default matches common TIFF, PNG, JPEG, and BMP files."
        ),
    )
    parser.add_argument(
        "--keep-csv",
        action="store_true",
        help="Keep the intermediate CSV exported by ImageJ instead of deleting it.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the ImageJ command that would run without executing it.",
    )
    return parser.parse_args(argv)


def ensure_imagej_path(path_arg: Path | None) -> Path:
    if path_arg is not None:
        return path_arg
    env_path = os.environ.get("IMAGEJ_PATH")
    if env_path:
        return Path(env_path)
    raise ValueError(
        "ImageJ executable path is required. Provide --imagej or set IMAGEJ_PATH."
    )


def validate_inputs(input_dir: Path, extensions: list[str] | tuple[str, ...]) -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: {input_dir}")

    normalized_exts = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in extensions}
    candidates = [p for p in input_dir.iterdir() if p.is_file()]
    matches = [p for p in candidates if p.suffix.lower() in normalized_exts]

    if not matches:
        raise FileNotFoundError(
            "No images with the requested extensions were found in the input directory."
        )

    return matches


def ij1_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\"", "\\\"")


def build_macro_text(input_dir: Path, output_csv: Path, extensions: list[str]) -> str:
    escaped_dir = ij1_escape(str(input_dir))
    escaped_csv = ij1_escape(str(output_csv))
    normalized_exts = [ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in extensions]
    ext_literals = ", ".join(f'"{ij1_escape(ext)}"' for ext in normalized_exts)

    macro = dedent(
        f"""
        requires("1.53f");
        dir = "{escaped_dir}";
        if (!endsWith(dir, File.separator)) dir = dir + File.separator;
        output = "{escaped_csv}";
        allowed = newArray({ext_literals});

        setBatchMode(true);
        run("Set Measurements...", "mean decimal=4");
        run("Clear Results");

        list = getFileList(dir);
        for (i = 0; i < list.length; i++) {{
            name = list[i];
            if (File.isDirectory(dir + name)) continue;
            lower = toLowerCase(name);
            keep = false;
            for (j = 0; j < allowed.length; j++) {{
                if (endsWith(lower, allowed[j])) {{
                    keep = true;
                    break;
                }}
            }}
            if (!keep) continue;

            open(dir + name);
            run("Measure");
            close();
            setResult("Label", nResults - 1, name);
        }}

        if (nResults == 0) {{
            exit("No measurements were generated.");
        }}

        saveAs("Results", output);
        """
    ).strip()

    return macro + "\n"


def run_imagej(imagej_path: Path, macro_path: Path, dry_run: bool = False) -> None:
    command = [str(imagej_path), "--headless", "--console", "-macro", str(macro_path)]
    if dry_run:
        print("Dry run: would execute", " ".join(command))
        return

    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        raise ImageJError(
            "ImageJ exited with a non-zero status.\n"
            f"Command: {' '.join(command)}\n"
            f"Stdout:\n{process.stdout}\n"
            f"Stderr:\n{process.stderr}"
        )

    if process.stderr:
        print(process.stderr, file=sys.stderr)
    if process.stdout:
        print(process.stdout)


def load_results(csv_path: Path) -> pd.DataFrame:
    try:
        with csv_path.open("r", newline="") as handle:
            # ImageJ writes CSVs with comma separators and plain headers.
            reader = csv.reader(handle)
            rows = list(reader)
    except FileNotFoundError as exc:
        raise ImageJError("ImageJ did not create the expected results CSV file.") from exc

    if len(rows) <= 1:
        raise ImageJError("The results CSV is empty. No measurements were recorded.")

    df = pd.read_csv(csv_path)
    columns = list(df.columns)
    if "Label" in columns:
        df = df.rename(columns={"Label": "Image"})
    if "Mean" not in df.columns:
        raise ImageJError("The results CSV does not contain a 'Mean' column.")
    return df[[col for col in df.columns if col in ("Image", "Mean")]]


def write_excel(df: pd.DataFrame, output_excel: Path) -> None:
    output_excel.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_excel, index=False)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        imagej_path = ensure_imagej_path(args.imagej_path)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    try:
        matching_files = validate_inputs(args.input_dir, args.extensions)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(exc, file=sys.stderr)
        return 2

    extensions = [ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in args.extensions]
    print(f"Found {len(matching_files)} image(s) to process.")

    with TemporaryDirectory(prefix="imagej_macro_") as temp_dir:
        temp_dir_path = Path(temp_dir)
        macro_path = temp_dir_path / "measure_mean.ijm"
        csv_path = temp_dir_path / "results.csv"

        macro_text = build_macro_text(args.input_dir, csv_path, extensions)
        macro_path.write_text(macro_text, encoding="utf-8")

        try:
            run_imagej(imagej_path, macro_path, dry_run=args.dry_run)
        except ImageJError as exc:
            print(exc, file=sys.stderr)
            return 1

        if args.dry_run:
            print("Dry run complete; no files were generated.")
            return 0

        df = load_results(csv_path)
        write_excel(df, args.output_excel)

        if args.keep_csv:
            target_csv = args.output_excel.with_suffix(".csv")
            csv_path.replace(target_csv)
            print(f"Kept intermediate CSV at {target_csv}")

    print(f"Wrote mean intensity measurements to {args.output_excel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
