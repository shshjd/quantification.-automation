# Image Quantification Automation

This repository contains a command-line tool for macOS that automates a common image quantification workflow. The program walks you through configuration (input folder, thresholding method, measurements, and Excel export location) before processing images.

## Requirements

Install the Python dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## Usage

Run the script and answer the prompts to configure the workflow:

```bash
python3 quantify_images.py
```

The program will:

1. Ask for the folder containing images.
2. Ask any additional questions needed to fully configure the run, including threshold method, measurements, and Excel output path.
3. Convert each image to grayscale (black and white) and, when thresholding is enabled, create a binary mask.
4. Convert the processed pixels to 32-bit floating point data.
5. Compute the requested measurements for every image.
6. Export the measurements to an Excel workbook.

Supported image formats include PNG, JPG, JPEG, TIFF, and BMP. The resulting Excel workbook is saved to the location you choose during configuration.
