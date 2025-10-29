# ImageJ Mean Intensity Automation Project

This project provides a ready-to-use folder structure, ImageJ macro, and helper script for measuring the mean intensity of multiple images via ImageJ's headless mode.

## Project Layout

```
.
├── input_images/     # Place the images to be processed here
├── macros/
│   └── mean_intensity.ijm
├── results/          # Output CSV files from ImageJ
├── run_logs/         # Log entries created per run
└── run_macro.sh      # Convenience script to trigger headless processing
```

## Macro Overview

The `macros/mean_intensity.ijm` script:

- Ensures ImageJ is configured to measure **mean intensity** with six decimals and no scaling when converting to 32-bit.
- Iterates over every supported image file in the input directory (TIFF, PNG, JPEG, BMP, GIF).
- Converts each image to 32-bit, measures the whole image, and appends the measurement to the Results table.
- Saves a timestamped CSV of the Results table in the `results/` directory.
- Logs each processed image and the saved results path to `run_logs/run.log`.

Arguments can be passed to the macro as comma-separated key/value pairs (`input=`, `output=`, `log=`) so the same script can be reused with alternative directories.

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

The script assumes ImageJ is installed at `/Applications/ImageJ/ImageJ.app/Contents/MacOS/ImageJ`. If your installation lives elsewhere, set the `IMAGEJ_APP` environment variable before running:

```bash
IMAGEJ_APP="/path/to/ImageJ" ./run_macro.sh
```

You can also run ImageJ manually without the helper script:

```bash
/Applications/ImageJ/ImageJ.app/Contents/MacOS/ImageJ \
  --headless \
  -macro "$(pwd)/macros/mean_intensity.ijm" \
  "input=$(pwd)/input_images,output=$(pwd)/results,log=$(pwd)/run_logs"
```

## Validating the Workflow

1. Place a few sample images in `input_images/`.
2. Run the macro headlessly or via the helper script.
3. Compare the generated CSV against manual measurements performed in ImageJ.

Each run appends to `run_logs/run.log` with timestamps so you can keep track of processed files.
