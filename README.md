# ImageJ Mean Intensity Automation Project

This project packages an ImageJ macro and an interactive helper script for measuring the mean intensity of multiple images via ImageJ's headless mode. Rather than relying on preset folders, the script prompts you for the directories to use at runtime.

## Macro Overview

The `macros/mean_intensity.ijm` script:

- Ensures ImageJ is configured to measure **mean intensity** with six decimals and no scaling when converting to 32-bit.
- Iterates over every supported image file in the chosen input directory (TIFF, PNG, JPEG, BMP, GIF).
- Converts each image to 32-bit, measures the whole image, and appends the measurement to the Results table.
- Saves a timestamped CSV of the Results table in your selected results directory.
- Logs each processed image and the saved results path to the designated log directory.

All three directories (`input`, `output`, and `log`) must be provided as comma-separated key/value arguments (`input=`, `output=`, `log=`) when the macro is invoked. The helper script described below collects these paths for you.

## One-Time ImageJ Preferences

Before running the macro, open ImageJ normally and configure:

1. **Edit → Options → Conversions** → uncheck *Scale when converting*.
2. **Analyze → Set Measurements…** → select only *Mean*, set *Decimal Places* to 6.

These preferences ensure identical results between manual and automated measurements.

## Running Headlessly

On macOS, execute the helper script:

```bash
./run_macro.sh
```

You will be prompted for:

1. The directory that contains the images to measure.
2. The directory where the results CSV should be saved.
3. The directory where run logs should be written.

The prompts default to the project’s own `input_images`, `results`, and `run_logs` folders (regardless of where you launch the script from). Press **Enter** to accept a suggested path or provide any other directory. If a supplied directory does not exist, the script offers to create it.

Before ImageJ launches, the script lists every supported image it finds in the chosen input directory. If no compatible files are present, it stops immediately with an error so you know why nothing ran. After the headless run finishes, it prints the last ten log entries so you can see which images were processed and whether any were skipped.

By default the helper script looks for the native macOS binary at `/Applications/ImageJ.app/Contents/MacOS/ImageJ-macosx` and falls back to the launcher script if necessary. If your installation lives elsewhere—or if ImageJ opens a GUI instead of running headlessly—point `IMAGEJ_APP` at the correct executable before launching:

```bash
IMAGEJ_APP="/path/to/ImageJ" ./run_macro.sh
```

You can also run ImageJ manually without the helper script:

```bash
/Applications/ImageJ/ImageJ.app/Contents/MacOS/ImageJ \
  --headless \
  -macro "$(pwd)/macros/mean_intensity.ijm" \
  "input=/path/to/images,output=/path/to/results,log=/path/to/logs"
```

## Validating the Workflow

1. Place a few sample images in the input directory of your choice.
2. Run the macro headlessly or via the helper script.
3. Compare the generated CSV against manual measurements performed in ImageJ.

Each run appends to the specified `run.log` with timestamps so you can keep track of processed files, skipped items, and any errors that occurred.
