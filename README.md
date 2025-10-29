# ImageJ Mean Intensity Automation

This project provides a cross-platform command-line helper that drives
[ImageJ](https://imagej.nih.gov/ij/) (or Fiji) in headless mode to collect the
mean pixel intensity for every image in a folder. The measurements are exported
to a Microsoft Excel workbook so they can be shared or analysed further.

## Requirements

* Python 3.9 or newer
* ImageJ or Fiji installation that supports the `--headless` flag
* The Python packages listed in [`requirements.txt`](requirements.txt)

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```
python -m src.imagej_mean_intensity INPUT_DIR OUTPUT.xlsx --imagej /path/to/ImageJ
```

* `INPUT_DIR` – directory that contains the images to process (no recursion).
* `OUTPUT.xlsx` – destination Excel workbook (will be overwritten).
* `--imagej` – path to the ImageJ executable. You can set the environment
  variable `IMAGEJ_PATH` instead of passing this flag on every run.

The tool filters files by extension (TIFF, PNG, JPEG, BMP by default). You can
override the list of extensions with `--extensions .tif .tiff`.

### Example

```bash
python -m src.imagej_mean_intensity ./images results.xlsx --imagej ~/Fiji.app/ImageJ-linux64
```

### Dry runs

Add `--dry-run` to see the ImageJ command that would be executed without
creating any files. Combine it with `--keep-csv` if you want to retain the raw
CSV produced by ImageJ alongside the Excel workbook.

## How it works

1. The script discovers eligible images in the folder.
2. It writes a temporary ImageJ macro that measures each image's mean intensity.
3. ImageJ runs headlessly with the generated macro and exports a CSV results
   table.
4. The CSV is converted to an Excel workbook (`.xlsx`) containing two columns:
   * **Image** – original filename
   * **Mean** – the mean pixel intensity reported by ImageJ

If ImageJ fails or produces no measurements, the script reports the error so
you can adjust the inputs and try again.
