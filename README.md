# ImageJ Automation Tool for macOS

This repository provides a command-line helper that automates ImageJ measurements on macOS.
The tool launches the user’s own `ImageJ.app` in headless mode when possible, or falls back to
AppleScript-driven batch mode when headless execution is unsupported. It generates an ImageJ
macro that processes every image in a chosen folder, converts them to binary masks, computes
measurements, and saves the resulting table to a CSV file.

## Requirements

* macOS with [ImageJ](https://imagej.nih.gov/ij/) installed (typically `/Applications/ImageJ.app`).
* Python 3.9 or later.

No third-party Python packages are required.

## Usage

1. Ensure ImageJ launches correctly on your Mac.
2. Collect the images you want to measure inside a single folder.
3. Run the automation script:

   ```bash
   python3 quantify_images.py
   ```

4. Answer the interactive prompts:
   * **ImageJ path** – The full path to the ImageJ executable inside the app bundle
     (for example `/Applications/ImageJ.app/Contents/MacOS/ImageJ`). The default is auto-detected
     when the executable exists at the standard location.
   * **Image folder** – Directory that contains the images to process. The tool scans only the
     top-level files with the extensions `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, or `.bmp`.
   * **Output CSV** – Destination for the measurement table. The file is overwritten if it already
     exists.
   * **Threshold method** – Choose between Otsu automatic thresholding or a user-supplied manual
     threshold (0–255).

5. The script creates a temporary macro with the requested configuration and attempts to run:
   * **Headless mode** – Executes ImageJ with the command
     `/Applications/ImageJ.app/Contents/MacOS/ImageJ --headless --macro <macro.ijm>`.
     On success, the CSV file is validated to confirm measurement data is present.
   * **AppleScript fallback** – If headless mode fails or produces no data, the tool offers to
     automate ImageJ through AppleScript. The automation opens ImageJ, triggers **File → Run
     Macro…**, waits for the results file to be written, and quits ImageJ automatically.

6. After ImageJ finishes, the script verifies that the CSV exists and contains measurement data
   before reporting success.

## Error handling

If ImageJ cannot run headlessly or returns without producing data, the tool prints the exact
command it attempted and suggests the AppleScript fallback. AppleScript automation is also
validated—if the CSV is missing or empty, the script reports the failure so you can investigate
further.

## Macro workflow

The generated ImageJ macro performs the following steps for every supported file in the selected
folder:

1. Open the image.
2. Convert it to 8-bit.
3. Apply the chosen threshold (Otsu or manual), converting the image to a binary mask.
4. Convert the mask to 32-bit.
5. Run **Measure** to capture area, mean, standard deviation, minimum, and maximum statistics.
6. After all images are processed, save the Results table to the requested CSV file.

This ensures the automation finishes cleanly—regardless of whether ImageJ succeeds in headless
mode or requires GUI automation—while leaving behind a verified measurement CSV for downstream
analysis.
