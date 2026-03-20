import json
import warnings

# Open the input file
with open("./scrapers/plotlist_nya", "r") as f:
    # Read each line
    for line in f:
        # Extract the values from the line
        a, b, c = line.strip().split('"')[1::2]
        a, b = a.lower(), b.lower()
        if c[0] == "'":
            c = c[1:]
        if c[-1] == "'":
            c = c[:-1]
        c = (
            c.replace("'yy'", "%Y")
            .replace("'y'", "%y")
            .replace("'mm'", "%m")
            .replace("'dd'", "%d")
            .replace("'yymmdd'", "%Y%m%d")
            .replace("'ymmdd'", "%y%m%d")
            .replace("'ymm'", "%y%m")
            .replace("'yy-mm-dd'", "%Y-%m-%d")
            .replace("'yymm'", "%Y%m")
            .replace("'yymmdd_113800'", "%Y%m%d_113800")
            .replace("'ymmdd_080000'", "%y%m%d_080000")
            .replace("'ymmdd113800'", "%y%m%d113800")
            .replace("'ymmdd_120000'", "%y%m%d_120000")
            .replace("'ymmdd_160000'", "%y%m%d_160000")
        )
        # Create the data structure
        data = {
            "id": b,
            "sites": ["nya"],
            "instruments": [b.split("_")[0]],
            "description": "",
            "path": c,
        }
        if "'" in a + b + c:
            warnings.warn(a + b + c)
        # Write the data to a new file
        with open(f"./scrapers/test/{b}.json", "w") as outfile:
            json.dump(data, outfile, indent=4)
