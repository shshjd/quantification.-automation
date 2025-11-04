# Fiji Batch Quantification Automation

This repository provides a minimal workflow for quantifying many images with [Fiji](https://fiji.sc/) in a single, automated run. The macro converts every image to 32-bit grayscale, measures area and integrated density, and writes the results to a CSV file.

## Contents

- `macros/batch_area_measurement.ijm` — Fiji macro that performs the batch processing.
- `scripts/run_batch_quant.sh` — Convenience wrapper that launches Fiji headlessly with the macro.

## Prerequisites

- macOS with Fiji installed. (The macro and script also work on Linux/Windows, but the wrapper has been tested on macOS.)
- A plain-text file that lists the images you want to quantify, with one absolute path per line. Example:

  ```text
  /Users/you/data/sample-01.tif
  /Users/you/data/sample-02.tif
  ```

## Running the batch quantification on macOS

1. **Locate the Fiji executable.** On macOS the binary lives inside the app bundle. The default path is:
   ```text
   /Applications/Fiji.app/Contents/MacOS/ImageJ-macosx
   ```
   If you installed Fiji elsewhere, adjust the path accordingly.

2. **Prepare your list file** with one full image path per line, as shown above. Relative paths are allowed but must be resolvable from the working directory where you launch the script.

3. **Run the wrapper script** from the repository root:
   ```bash
   ./scripts/run_batch_quant.sh \
     /Applications/Fiji.app/Contents/MacOS/ImageJ-macosx \
     /path/to/image-list.txt \
     /path/to/output-results.csv
   ```

   The script assembles the required macro arguments, so paths containing spaces are handled correctly. Fiji runs in headless mode, opens each image, converts it to 32-bit grayscale, records the measurements, and saves the output CSV to the location you specify.

4. **Review the output CSV.** It contains Fiji's standard measurement columns, including `Area` and `IntDen` (integrated density) for every processed image.

## Interactive use (optional)

If you run the macro directly inside the Fiji GUI (`Plugins → Macros → Run...`), it will prompt you to choose the list file and where to save the results.

## Troubleshooting

- The macro skips missing files but logs their paths to the Fiji Log window. Double-check the list file if entries are skipped.
- Ensure Fiji has read/write access to the directories that contain your images and the output CSV, especially when working with external drives on macOS.

