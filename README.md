# Fiji Batch Quantification Automation

This repository provides a minimal workflow for quantifying many images with
[Fiji](https://fiji.sc/) in a single, automated run. The original macro converts
every image to 32-bit grayscale, measures area and integrated density, and
writes the results to a CSV file.

The project now also includes a pure Python reimplementation so the workflow can
be executed without Fiji or the macOS-only shell script.

## Contents

- `macros/batch_area_measurement.ijm` — Fiji macro that performs the batch
  processing.
- `scripts/run_batch_quant.py` — Python script that replicates the macro's logic
  using Pillow and NumPy.
- `scripts/run_batch_quant.sh` — Original convenience wrapper that launches
  Fiji headlessly with the macro (kept for reference).
- `requirements.txt` — Python dependencies required by `run_batch_quant.py`.

## Prerequisites (Python version)

- Python 3.9 or later.
- Install the required libraries:
  ```bash
  python -m pip install -r requirements.txt
  ```
- A plain-text file that lists the images you want to quantify, with one path
  per line. Relative paths are resolved from the location of this list file.
  Example:
  ```text
  /Users/you/data/sample-01.tif
  ../data/sample-02.tif
  ```

## Running the Python batch quantification

1. **Prepare your list file** with one image path per line as shown above.
2. **Run the Python script** from the repository root (or anywhere else):
   ```bash
   python scripts/run_batch_quant.py \
     /path/to/image-list.txt \
     /path/to/output-results.csv
   ```
   Use `--decimal-places` if you want to change the precision of the output
   values (defaults to three decimal places).
3. **Review the output CSV.** It contains three columns: the image path, the
   measured area (number of pixels), and the integrated density (sum of pixel
   intensities after conversion to 32-bit grayscale).

Any images that cannot be processed are reported on stderr. The script exits
with a non-zero status code if no images could be processed successfully.

## Running the batch quantification on macOS with Fiji (legacy workflow)

1. **Locate the Fiji executable.** On macOS the binary lives inside the app
   bundle. The default path is:
   ```text
   /Applications/Fiji.app/Contents/MacOS/ImageJ-macosx
   ```
   If you installed Fiji elsewhere, adjust the path accordingly.

2. **Prepare your list file** with one full image path per line, as shown above.
   Relative paths are allowed but must be resolvable from the working directory
   where you launch the script.

3. **Run the wrapper script** from the repository root:
   ```bash
   ./scripts/run_batch_quant.sh \
     /Applications/Fiji.app/Contents/MacOS/ImageJ-macosx \
     /path/to/image-list.txt \
     /path/to/output-results.csv
   ```

   The script assembles the required macro arguments, so paths containing spaces
   are handled correctly. Fiji runs in headless mode, opens each image, converts
   it to 32-bit grayscale, records the measurements, and saves the output CSV to
   the location you specify.

4. **Review the output CSV.** It contains Fiji's standard measurement columns,
   including `Area` and `IntDen` (integrated density) for every processed image.

## Interactive use (optional)

If you run the macro directly inside the Fiji GUI (`Plugins → Macros → Run...`),
it will prompt you to choose the list file and where to save the results.

## Troubleshooting

- The macro skips missing files but logs their paths to the Fiji Log window.
  Double-check the list file if entries are skipped.
- Ensure Fiji has read/write access to the directories that contain your images
  and the output CSV, especially when working with external drives on macOS.
- For the Python script, verify that the listed images are supported by Pillow
  and that the dependencies from `requirements.txt` are installed.
