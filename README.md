# Image Quantification Automation

This repository contains a command-line tool for macOS that automates an image quantification workflow **using your existing Ima
geJ or Fiji installation**. The program collects every piece of configuration it needs—ImageJ location, image folder, thresholdin
g method, measurements, and Excel export destination—before a single image is processed.

## Requirements

1. A working copy of [ImageJ](https://imagej.nih.gov/ij/) or [Fiji](https://imagej.net/software/fiji/) installed on your Mac. The
 script runs ImageJ headlessly, so make sure it launches normally before using the automation.
2. Python 3.9+ with the `openpyxl` package:

```bash
python3 -m pip install -r requirements.txt
```

> 💡 **Tip:** If you do not already have the package installed system-wide, consider creating a virtual environment first:
>
> ```bash
> python3 -m venv .venv
> source .venv/bin/activate
> python3 -m pip install -r requirements.txt
> ```

## Usage

1. Confirm ImageJ or Fiji opens correctly on your machine (double-click the application and make sure it starts without errors).
2. Place all images you want to quantify in a single folder. Supported formats include `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`,
 and `.bmp`.
3. Run the script and answer the prompts:

```bash
python3 quantify_images.py
```

### Interactive configuration walkthrough

When you run the command, the script asks a series of questions so it can fully configure itself before launching ImageJ:

1. **ImageJ application path** – Paste the `.app` bundle (for example `/Applications/Fiji.app`) or the executable inside `Content
s/MacOS`. The script automatically resolves the actual binary that will be launched headlessly.
2. **Image folder** – Provide the directory containing the images to process. Only the top-level files in that folder are touched
; subdirectories are ignored.
3. **Threshold method** – Choose one of the following:
   * `none` – Convert to grayscale and 32-bit but do not limit measurements to a thresholded region.
   * `otsu` – Use ImageJ’s Otsu auto-threshold and limit measurements to the resulting mask.
   * `manual` – Supply an explicit lower threshold between 0 and 255. Measurements are limited to pixels above this threshold.
4. **Measurements** – Enter a comma-separated list of measurement keys. Press enter to accept the default set (`mean_intensity`, `
std_dev`, `sum_intensity`, `foreground_area`). Each key maps directly to ImageJ measurements:
   * `mean_intensity` → Mean
   * `std_dev` → Standard Deviation
   * `sum_intensity` → Integrated Density
   * `foreground_area` → Area (pixel count)
   * `min_intensity` → Minimum intensity
   * `max_intensity` → Maximum intensity
5. **Excel output path** – Accept the suggested destination inside your image folder or supply another `.xlsx` path. The director
y is created automatically when it doesn’t exist.
6. **Confirmation** – Review a summary of your selections and type `y` to start processing. Typing anything else cancels the run b
efore ImageJ launches.

After confirmation the script will:

1. Generate an ImageJ macro tailored to your answers.
2. Run ImageJ in headless mode to process every supported image in the chosen folder.
3. For each file, convert it to 8-bit grayscale, apply the selected threshold (if any), convert to 32-bit, and run the requested m
easur
ements with ImageJ’s measurement engine.
4. Export ImageJ’s results table to a temporary CSV file and convert it into an Excel workbook at your chosen destination.

### Understanding the Excel report

The workbook contains a single sheet named **Measurements**. Each row corresponds to a processed image and includes:

| Column | Description |
| ------ | ----------- |
| `Image` | The filename processed by ImageJ. |
| `Threshold Applied` | The lower threshold value used, or `-` when no threshold was applied. |
| Measurement columns | One column per measurement you selected (e.g., *Mean Intensity*, *Foreground Area (px)*). |

You can re-run the program on the same folder at any time—existing Excel files are overwritten only after a successful export.

If you need to adapt the workflow (for example, additional ImageJ measurements or nested folder traversal), feel free to share th
e desired changes and they can be incorporated into a follow-up script update.
