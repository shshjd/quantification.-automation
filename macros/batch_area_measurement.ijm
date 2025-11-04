macro "Batch Area Measurement" {
    listPath = File.openDialog("Select text file with image paths");
    if (listPath == null || listPath == "") {
        exit("No path list selected.");
    }

    contents = File.openAsString(listPath);
    if (lengthOf(contents) == 0) {
        exit("The selected file is empty.");
    }

    paths = split(contents, "\n");

    useFloat = getBoolean("Convert images to 32-bit? (Cancel for 8-bit)");

    outputPath = File.saveDialog("Save results table", "batch-area-measurements.csv");
    if (outputPath == null || outputPath == "") {
        exit("No output location selected.");
    }

    run("Clear Results");
    setBatchMode(true);
    run("Set Measurements...", "area integrated redirect=None decimal=3");

    for (i = 0; i < paths.length; i++) {
        path = replace(paths[i], "\r", "");
        if (path == "")
            continue;
        if (!File.exists(path)) {
            print("Skipping missing file: " + path);
            continue;
        }

        open(path);
        if (useFloat)
            run("32-bit");
        else
            run("8-bit");
        run("Grays");
        run("Measure");
        close();
    }

    setBatchMode(false);
    saveAs("Results", outputPath);
    print("Saved results to: " + outputPath);
}
