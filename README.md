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

The prompts display the current working directory's `input_images`, `results`, and `run_logs` folders as suggestions. You can press **Enter** to accept a suggested path or provide any other directory. If a supplied directory does not exist, the script offers to create it.

The script assumes ImageJ is installed at `/Applications/ImageJ/ImageJ.app/Contents/MacOS/ImageJ`. If your installation lives elsewhere, set the `IMAGEJ_APP` environment variable before running:

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

Each run appends to the specified `run.log` with timestamps so you can keep track of processed files.
