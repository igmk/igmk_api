"""Plot image serving and plot metadata.

A plot config carries either a single ``path`` (legacy, treated as daily) or a
``paths`` object keyed by granularity. Templates are Python ``strftime``
templates resolved against the requested date, and resolve to either a local
file or an ``http(s)://`` URL.
"""

import datetime
import fnmatch
import json
import os
from io import BytesIO

import requests
from flask import send_file

from igmk_api.settings import settings

GRANULARITY_FORMATS = {
    "daily": "%Y%m%d",
    "monthly": "%Y%m",
    "seasonal": "%Y%m",
    "yearly": "%Y",
}


def _plot_paths(config):
    return config.get("paths") or {"daily": config["path"]}


def _plot_granularities(config):
    paths = _plot_paths(config)
    return [g for g in GRANULARITY_FORMATS if g in paths]


class _PlotError(Exception):
    def __init__(self, body, status):
        self.body = body
        self.status = status


def _resolve_plot(visID, granularity, dateString):
    """Validate visID/granularity/dateString and return (config, paths, date).
    Raises _PlotError (with a JSON body + status) on any validation failure."""
    if granularity not in GRANULARITY_FORMATS:
        raise _PlotError(
            {"error": f"Unknown granularity '{granularity}', expected one of {list(GRANULARITY_FORMATS)}"}, 400
        )
    with open(settings.plots_dir / f"{visID}.json") as f:
        config = json.load(f)
    paths = _plot_paths(config)
    if granularity not in paths:
        raise _PlotError({"error": f"Plot '{visID}' does not support granularity '{granularity}'"}, 404)
    try:
        date = datetime.datetime.strptime(dateString, GRANULARITY_FORMATS[granularity])
    except ValueError:
        raise _PlotError({
            "error": f"dateString '{dateString}' does not match expected format "
            f"'{GRANULARITY_FORMATS[granularity]}' for granularity '{granularity}'"
        }, 400)
    return config, paths, date


def _serve_plot(visID, granularity, dateString):
    try:
        config, paths, date = _resolve_plot(visID, granularity, dateString)
    except _PlotError as e:
        return e.body, e.status
    if config.get("multi"):
        return {
            "error": f"Plot '{visID}' has multiple items per date; "
            f"use /visualizations/byID/{visID}/{granularity}/{dateString}/items instead"
        }, 400
    image_path = date.strftime(paths[granularity])

    if image_path.startswith("http://") or image_path.startswith("https://"):
        response = requests.get(image_path)
        return send_file(BytesIO(response.content), mimetype="image/png")
    else:
        with open(image_path, "rb") as f:
            return send_file(BytesIO(f.read()), mimetype="image/png")


def return_image(visID, dateString):
    return _serve_plot(visID, "daily", dateString)


def return_image_granular(visID, granularity, dateString):
    return _serve_plot(visID, granularity, dateString)


def return_current_image(visID):
    return _serve_plot(visID, "daily", datetime.date.today().strftime("%Y%m%d"))


def _list_multi_items(config, paths, granularity, date):
    """Return the sorted list of item filenames for a multi-item plot on `date`."""
    directory = date.strftime(paths[granularity])
    if directory.startswith("http://") or directory.startswith("https://"):
        raise _PlotError({"error": "Listing items is not supported for remote plot sources"}, 501)
    pattern = date.strftime(config.get("pattern", "*.png"))
    try:
        filenames = sorted(fnmatch.filter(os.listdir(directory), pattern))
    except FileNotFoundError:
        filenames = []
    return directory, filenames


def return_plot_items(visID, granularity, dateString):
    try:
        config, paths, date = _resolve_plot(visID, granularity, dateString)
        if not config.get("multi"):
            raise _PlotError({"error": f"Plot '{visID}' is not a multi-item plot"}, 400)
        _, filenames = _list_multi_items(config, paths, granularity, date)
    except _PlotError as e:
        return e.body, e.status
    return {"count": len(filenames)}, 200


def return_plot_item_image(visID, granularity, dateString, itemIndex):
    try:
        itemIndex = int(itemIndex)
    except ValueError:
        return {"error": f"itemIndex must be an integer, got '{itemIndex}'"}, 400
    try:
        config, paths, date = _resolve_plot(visID, granularity, dateString)
        if not config.get("multi"):
            raise _PlotError({"error": f"Plot '{visID}' is not a multi-item plot"}, 400)
        directory, filenames = _list_multi_items(config, paths, granularity, date)
    except _PlotError as e:
        return e.body, e.status
    if not (0 <= itemIndex < len(filenames)):
        return {"error": f"No item at index {itemIndex}; {len(filenames)} item(s) available for this date"}, 404
    with open(os.path.join(directory, filenames[itemIndex]), "rb") as f:
        return send_file(BytesIO(f.read()), mimetype="image/png")


def return_plots_by_instrument(instrumentID):
    plots = []
    dir = str(settings.plots_dir)
    for filename in os.listdir(dir):
        f = os.path.join(dir, filename)
        with open(f) as plots_config_file:
            plots_file = json.load(plots_config_file)
        for instrument in plots_file["instruments"]:
            if instrument == instrumentID:
                plots.append({
                    "id": plots_file["id"],
                    "granularities": _plot_granularities(plots_file),
                    "multi": bool(plots_file.get("multi", False)),
                })
    return plots
