// mean_intensity.ijm
// Batch mean intensity measurement macro for ImageJ headless execution.
//
// Usage examples:
//   ImageJ --headless -macro /path/to/macros/mean_intensity.ijm
//   ImageJ --headless -macro /path/to/macros/mean_intensity.ijm "input=/path/to/input,output=/path/to/results"
//   ImageJ --headless -macro /path/to/macros/mean_intensity.ijm "input=/input,output=/output,log=/logs"
//
// Arguments (optional, comma separated):
//   input  - Directory that contains source images.
//   output - Directory where the results CSV will be written.
//   log    - Directory where run logs will be appended.
//
// When arguments are omitted the macro uses the project directories
// located one level above the macro file:
//   ../input_images/
//   ../results/
//   ../run_logs/
//
// The macro will:
//   * Configure measurement options for mean intensity with six decimals.
//   * Disable scaling during conversions to preserve intensity values.
//   * Convert every image to 32-bit.
//   * Measure the entire image (no ROI).
//   * Save the results table as CSV in the results directory.
//   * Write a log entry per processed file.

macro "Batch Mean Intensity" {
    setBatchMode(true);

    defaultRoot = File.getParent(getDirectory("macro"));
    defaultInput = defaultRoot + "input_images" + File.separator;
    defaultOutput = defaultRoot + "results" + File.separator;
    defaultLog = defaultRoot + "run_logs" + File.separator;

    args = getArgument();
    parsed = parseArguments(args, defaultInput, defaultOutput, defaultLog);
    inputDir = parsed[0];
    outputDir = parsed[1];
    logDir = parsed[2];

    ensureDirectory(inputDir);
    ensureDirectory(outputDir);
    ensureDirectory(logDir);

    run("Clear Results");
    run("Set Measurements...", "mean redirect=None decimal=6");
    setOption("Redirect None", true);
    setOption("ScaleConversions", false);

    fileList = getFileList(inputDir);
    processedCount = 0;

    for (i = 0; i < fileList.length; i++) {
        name = fileList[i];
        path = inputDir + name;
        if (File.isDirectory(path))
            continue;
        if (!isImageFile(name))
            continue;

        logMessage = "Processing " + path;
        print(logMessage);
        appendLog(logDir, logMessage);

        open(path);
        run("32-bit");
        run("Measure");
        close();
        processedCount++;
    }

    if (processedCount == 0) {
        print("No image files found in " + inputDir);
        appendLog(logDir, "No image files processed from " + inputDir);
    }

    resultsPath = buildResultsPath(outputDir);
    saveAs("Results", resultsPath);
    appendLog(logDir, "Saved results to " + resultsPath);

    setBatchMode(false);
}

function parseArguments(argString, defaultInput, defaultOutput, defaultLog) {
    inputDir = defaultInput;
    outputDir = defaultOutput;
    logDir = defaultLog;

    if (argString != "") {
        entries = split(argString, ",");
        for (i = 0; i < entries.length; i++) {
            entry = trim(entries[i]);
            if (entry == "")
                continue;
            eq = indexOf(entry, "=");
            if (eq < 0)
                continue;
            key = trim(substring(entry, 0, eq));
            value = trim(substring(entry, eq + 1));
            if (value == "")
                continue;
            value = ensureTrailingSeparator(value);
            if (startsWith(key, "input"))
                inputDir = value;
            else if (startsWith(key, "output"))
                outputDir = value;
            else if (startsWith(key, "log"))
                logDir = value;
        }
    }

    return newArray(inputDir, outputDir, logDir);
}

function ensureDirectory(path) {
    if (!File.exists(path))
        File.makeDirectory(path);
}

function ensureTrailingSeparator(path) {
    if (endsWith(path, File.separator))
        return path;
    return path + File.separator;
}

function isImageFile(name) {
    lower = toLowerCase(name);
    return endsWith(lower, ".tif") || endsWith(lower, ".tiff") || endsWith(lower, ".png") ||
        endsWith(lower, ".jpg") || endsWith(lower, ".jpeg") || endsWith(lower, ".bmp") ||
        endsWith(lower, ".gif");
}

function appendLog(logDir, message) {
    timestamp = getTimestamp();
    File.append(timestamp + " " + message + "\n", logDir + "run.log");
}

function buildResultsPath(outputDir) {
    timestamp = getTimestamp();
    return outputDir + "mean_intensity_" + timestamp + ".csv";
}

function getTimestamp() {
    getDateAndTime(year, month, dayOfWeek, dayOfMonth, hour, minute, second, msec);
    return sprintf("%04d%02d%02d-%02d%02d%02d", year, month + 1, dayOfMonth, hour, minute, second);
}
