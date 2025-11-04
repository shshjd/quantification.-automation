macro "Batch Area Measurement" {
    args = getArgument();
    listPath = "";
    outputPath = "";

    if (args != "") {
        lines = split(args, "\n");
        for (i = 0; i < lines.length; i++) {
            line = replace(lines[i], "\r", "");
            if (line == "")
                continue;
            sep = indexOf(line, "=");
            if (sep < 0)
                continue;
            key = substring(line, 0, sep);
            value = substring(line, sep + 1, lengthOf(line));
            if (key == "list")
                listPath = value;
            else if (key == "output")
                outputPath = value;
        }

        if (listPath == "" || outputPath == "") {
            exit("Headless mode requires both 'list' and 'output' arguments.");
        }
    } else {
        listPath = File.openDialog("Select text file with image paths");
        if (listPath == null || listPath == "") {
            exit("No path list selected.");
        }
        outputPath = File.saveDialog("Save results table", "batch-area-measurements.csv");
        if (outputPath == null || outputPath == "") {
            exit("No output location selected.");
        }
    }

    contents = File.openAsString(listPath);
    if (lengthOf(contents) == 0) {
        exit("The selected file is empty.");
    }

    paths = split(contents, "\n");

    run("Clear Results");
    setBatchMode(true);
    run("Set Measurements...", "area mean standard integrated redirect=None decimal=3");

    for (i = 0; i < paths.length; i++) {
        path = replace(paths[i], "\r", "");
        if (path == "")
            continue;
        if (!File.exists(path)) {
            print("Skipping missing file: " + path);
            continue;
        }

        open(path);
        run("32-bit");
        run("Grays");
        run("Measure");
        close();
    }

    setBatchMode(false);
    saveAs("Results", outputPath);
    print("Saved results to: " + outputPath);
}
