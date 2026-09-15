"""Plot image serving and plot metadata.

A plot config carries either a single ``path`` (legacy, treated as daily) or a
``paths`` object keyed by granularity. Templates are Python ``strftime``
templates resolved against the requested date, and resolve to either a local
file or an ``http(s)://`` URL.
"""

import datetime
import fnmatch
import logging
import os
from io import BytesIO
from pathlib import Path

import requests
from flask import send_file

from igmk_api.config import iter_configs, read_config
from igmk_api.settings import settings

log = logging.getLogger(__name__)

GRANULARITY_FORMATS = {
    "daily": "%Y%m%d",
    "monthly": "%Y%m",
    "seasonal": "%Y%m",
    "yearly": "%Y",
}

#: (connect, read) seconds for fetching a remote plot image. 400 of the 445
#: plot configs resolve to the same upstream host, so an untimed request there
#: would let one slow origin exhaust the whole worker pool.
IMAGE_TIMEOUT = (5, 30)

_REMOTE_PREFIXES = ("http://", "https://")


def _error(body, status):
    """Return a JSON error body, content type spelled out.

    The image routes declare both ``image/png`` and ``application/json``, so
    Connexion cannot infer which applies and 500s with
    NonConformingResponseHeaders unless the handler names it in the headers.
    """
    return body, status, {"Content-Type": "application/json"}


class _PlotError(Exception):
    """Carries the JSON body and status a handler should return."""

    def __init__(self, body, status):
        super().__init__(body.get("error", ""))
        self.body = body
        self.status = status


def _is_remote(path):
    return path.startswith(_REMOTE_PREFIXES)


def _plot_paths(config):
    """Normalise legacy single-``path`` configs onto the ``paths`` shape."""
    paths = config.get("paths")
    if isinstance(paths, dict) and paths:
        return paths
    path = config.get("path")
    return {"daily": path} if isinstance(path, str) else {}


def _plot_granularities(config):
    paths = _plot_paths(config)
    return [g for g in GRANULARITY_FORMATS if g in paths]


def _resolve_plot(visID, granularity, dateString):
    """Validate visID/granularity/dateString and return (config, paths, date).

    Raises :class:`_PlotError` (with a JSON body + status) on any failure.
    """
    if granularity not in GRANULARITY_FORMATS:
        raise _PlotError(
            {
                "error": f"Unknown granularity '{granularity}', "
                f"expected one of {list(GRANULARITY_FORMATS)}"
            },
            400,
        )
    config = read_config(settings.plots_dir, visID)
    if config is None:
        raise _PlotError({"error": f"No plot '{visID}'"}, 404)
    paths = _plot_paths(config)
    if not paths:
        log.warning("plot config %r declares neither 'path' nor 'paths'", visID)
        raise _PlotError({"error": f"Plot '{visID}' declares no image paths"}, 404)
    if granularity not in paths:
        raise _PlotError(
            {"error": f"Plot '{visID}' does not support granularity '{granularity}'"}, 404
        )
    try:
        date = datetime.datetime.strptime(dateString, GRANULARITY_FORMATS[granularity])
    except ValueError as exc:
        raise _PlotError({
            "error": f"dateString '{dateString}' does not match expected format "
            f"'{GRANULARITY_FORMATS[granularity]}' for granularity '{granularity}'"
        }, 400) from exc
    return config, paths, date


def _send_image(image_path):
    """Serve a plot image from a local path or an upstream URL."""
    if _is_remote(image_path):
        try:
            response = requests.get(image_path, timeout=IMAGE_TIMEOUT)
        except requests.RequestException as exc:
            log.warning("plot source %s failed: %s", image_path, exc)
            raise _PlotError({"error": "Plot source is unavailable"}, 502) from exc
        if response.status_code == 404:
            raise _PlotError({"error": "No plot image for this date"}, 404)
        if not response.ok:
            log.warning("plot source %s returned %s", image_path, response.status_code)
            raise _PlotError({"error": "Plot source is unavailable"}, 502)
        return send_file(BytesIO(response.content), mimetype="image/png")

    path = Path(image_path)
    if not path.is_file():
        raise _PlotError({"error": "No plot image for this date"}, 404)
    return send_file(path, mimetype="image/png")


def _serve_plot(visID, granularity, dateString):
    try:
        config, paths, date = _resolve_plot(visID, granularity, dateString)
        if config.get("multi"):
            raise _PlotError({
                "error": f"Plot '{visID}' has multiple items per date; "
                f"use /visualizations/byID/{visID}/{granularity}/{dateString}/items instead"
            }, 400)
        return _send_image(date.strftime(paths[granularity]))
    except _PlotError as e:
        return _error(e.body, e.status)


def return_image(visID, dateString):
    return _serve_plot(visID, "daily", dateString)


def return_image_granular(visID, granularity, dateString):
    return _serve_plot(visID, granularity, dateString)


def return_current_image(visID):
    return _serve_plot(visID, "daily", datetime.date.today().strftime("%Y%m%d"))


def _list_multi_items(config, paths, granularity, date):
    """Return (directory, sorted item filenames) for a multi-item plot on `date`."""
    directory = date.strftime(paths[granularity])
    if _is_remote(directory):
        raise _PlotError({"error": "Listing items is not supported for remote plot sources"}, 501)
    pattern = date.strftime(config.get("pattern", "*.png"))
    try:
        filenames = sorted(fnmatch.filter(os.listdir(directory), pattern))
    except OSError:
        # No data directory for this date yet, or it is not readable -- an
        # empty day, not an error.
        filenames = []
    return directory, filenames


def _resolve_multi(visID, granularity, dateString):
    config, paths, date = _resolve_plot(visID, granularity, dateString)
    if not config.get("multi"):
        raise _PlotError({"error": f"Plot '{visID}' is not a multi-item plot"}, 400)
    return _list_multi_items(config, paths, granularity, date)


def return_plot_items(visID, granularity, dateString):
    try:
        _directory, filenames = _resolve_multi(visID, granularity, dateString)
    except _PlotError as e:
        return _error(e.body, e.status)
    return {"count": len(filenames)}, 200


def return_plot_item_image(visID, granularity, dateString, itemIndex):
    try:
        index = int(itemIndex)
    except (TypeError, ValueError):
        return _error({"error": f"itemIndex must be an integer, got '{itemIndex}'"}, 400)
    try:
        directory, filenames = _resolve_multi(visID, granularity, dateString)
        if not 0 <= index < len(filenames):
            raise _PlotError(
                {
                    "error": f"No item at index {index}; "
                    f"{len(filenames)} item(s) available for this date"
                },
                404,
            )
        return _send_image(os.path.join(directory, filenames[index]))
    except _PlotError as e:
        return _error(e.body, e.status)


def return_plots_by_instrument(instrumentID):
    """Every plot that lists *instrumentID*, as [{id, granularities, multi}]."""
    plots = []
    for _stem, config in iter_configs(settings.plots_dir):
        plot_id = config.get("id")
        if not plot_id or instrumentID not in (config.get("instruments") or []):
            continue
        plots.append({
            "id": plot_id,
            "granularities": _plot_granularities(config),
            "multi": bool(config.get("multi", False)),
        })
    return plots
