"""Free-text search across instruments, plots and sites."""

import json
from pathlib import Path

from igmk_api.settings import settings


def search(query):
    def search_jsons(query, dir, keys):
        query = query.lower()
        results = dict()
        for path in Path(dir).glob("*.json"):
            data = json.loads(path.read_text())
            if any(query in str(data.get(key, "")).lower() for key in keys):
                file = json.loads(path.read_text())
                fileKeys = list(file.keys())
                results[file[fileKeys[0]]] = file[fileKeys[1]]
        return results
    return dict(inst=search_jsons(query, settings.instruments_dir, ["name", "description"]), \
        plots=search_jsons(query, settings.plots_dir, ["id", "description"]), \
        sites=search_jsons(query, settings.sites_dir, ["siteID", "siteHumanReadable"]))
