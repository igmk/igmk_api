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

from igmk_api.config import load_configs, read_config
from igmk_api.settings import settings

log = logging.getLogger(__name__)

GRANULARITY_FORMATS = {
    "daily": "%Y%m%d",
    "monthly": "%Y%m",
    "seasonal": "%Y%m",
    "yearly": "%Y",
}

#: (connect, read) seconds for fetching a remote plot image.
IMAGE_TIMEOUT = (5, 30)

#: Nearly every remote plot lives on one host, so keep-alive saves a TCP+TLS
#: handshake per image.
_http = requests.Session()


class _PlotError(Exception):
    """A failure to serve a plot, carrying the status to respond with."""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.message = message
        self.status = status

    @property
    def response(self) -> tuple[dict[str, str], int, dict[str, str]]:
        # The image routes declare both image/png and application/json, so
        # Connexion cannot infer a content type and 500s unless we name it.
        return {"error": self.message}, self.status, {"Content-Type": "application/json"}


def _is_remote(path: str) -> bool:
    return path.startswith(("http://", "https://"))


def _plot_paths(config: dict) -> dict[str, str]:
    """Granularity -> strftime template, normalising legacy single-``path`` configs.

    Unknown granularities are dropped, so any key that survives is safe to look
    up in ``GRANULARITY_FORMATS``.
    """
    paths = config.get("paths")
    if not isinstance(paths, dict):
        path = config.get("path")
        paths = {"daily": path} if isinstance(path, str) else {}
    return {g: p for g, p in paths.items() if g in GRANULARITY_FORMATS and isinstance(p, str)}


def _plot_granularities(config: dict) -> list[str]:
    paths = _plot_paths(config)
    return [g for g in GRANULARITY_FORMATS if g in paths]


def _resolve_plot(
    visID: str, granularity: str, dateString: str
) -> tuple[dict, datetime.datetime, str]:
    """Load the plot config and resolve its template for the requested date.

    Returns ``(config, date, target)``, where *target* is a local path or a URL.
    Raises :class:`_PlotError` on any failure.
    """
    config = read_config(settings.plots_dir, visID)
    if config is None:
        raise _PlotError(f"No plot '{visID}'", 404)
    paths = _plot_paths(config)
    if not paths:
        log.warning("plot config %r declares no usable 'path' or 'paths'", visID)
        raise _PlotError(f"Plot '{visID}' declares no image paths", 404)
    if granularity not in paths:
        raise _PlotError(f"Plot '{visID}' does not support granularity '{granularity}'", 404)
    date_format = GRANULARITY_FORMATS[granularity]
    try:
        date = datetime.datetime.strptime(dateString, date_format)
    except ValueError as exc:
        raise _PlotError(
            f"dateString '{dateString}' does not match expected format "
            f"'{date_format}' for granularity '{granularity}'",
            400,
        ) from exc
    return config, date, date.strftime(paths[granularity])


def _send_image(image_path: str):
    """Serve a plot image from a local path or an upstream URL."""
    if _is_remote(image_path):
        try:
            response = _http.get(image_path, timeout=IMAGE_TIMEOUT)
        except requests.RequestException as exc:
            log.warning("plot source %s failed: %s", image_path, exc)
            raise _PlotError("Plot source is unavailable", 502) from exc
        if response.status_code == 404:
            raise _PlotError("No plot image for this date", 404)
        if not response.ok:
            log.warning("plot source %s returned %s", image_path, response.status_code)
            raise _PlotError("Plot source is unavailable", 502)
        return send_file(BytesIO(response.content), mimetype="image/png")

    path = Path(image_path)
    if not path.is_file():
        raise _PlotError("No plot image for this date", 404)
    return send_file(path, mimetype="image/png")


def _serve_plot(visID: str, granularity: str, dateString: str):
    try:
        config, _date, target = _resolve_plot(visID, granularity, dateString)
        if config.get("multi"):
            raise _PlotError(
                f"Plot '{visID}' has multiple items per date; use "
                f"/visualizations/byID/{visID}/{granularity}/{dateString}/items instead",
                400,
            )
        return _send_image(target)
    except _PlotError as e:
        return e.response


def plot_image(visID: str, dateString: str):
    return _serve_plot(visID, "daily", dateString)


def plot_image_granular(visID: str, granularity: str, dateString: str):
    return _serve_plot(visID, granularity, dateString)


def plot_image_today(visID: str):
    return _serve_plot(visID, "daily", datetime.date.today().strftime("%Y%m%d"))


def _multi_items(visID: str, granularity: str, dateString: str) -> tuple[str, list[str]]:
    """Return (directory, sorted item filenames) for a multi-item plot date."""
    config, date, directory = _resolve_plot(visID, granularity, dateString)
    if not config.get("multi"):
        raise _PlotError(f"Plot '{visID}' is not a multi-item plot", 400)
    if _is_remote(directory):
        raise _PlotError("Listing items is not supported for remote plot sources", 501)
    pattern = date.strftime(config.get("pattern", "*.png"))
    try:
        filenames = sorted(fnmatch.filter(os.listdir(directory), pattern))
    except OSError:
        # No data directory for this date yet -- an empty day, not an error.
        filenames = []
    return directory, filenames


def plot_items(visID: str, granularity: str, dateString: str):
    try:
        _directory, filenames = _multi_items(visID, granularity, dateString)
    except _PlotError as e:
        return e.response
    return {"count": len(filenames)}, 200


def plot_item_image(visID: str, granularity: str, dateString: str, itemIndex: int):
    try:
        directory, filenames = _multi_items(visID, granularity, dateString)
        # itemIndex is coerced to int and bounded below by openapi.yaml.
        if itemIndex >= len(filenames):
            raise _PlotError(
                f"No item at index {itemIndex}; "
                f"{len(filenames)} item(s) available for this date",
                404,
            )
        return _send_image(os.path.join(directory, filenames[itemIndex]))
    except _PlotError as e:
        return e.response


def plots_by_instrument(instrumentID: str) -> list[dict]:
    """Every plot that lists *instrumentID*, as [{id, granularities, multi}]."""
    plots = []
    for _stem, config in load_configs(settings.plots_dir):
        plot_id = config.get("id")
        if not plot_id or instrumentID not in (config.get("instruments") or []):
            continue
        plots.append({
            "id": plot_id,
            "granularities": _plot_granularities(config),
            "multi": bool(config.get("multi")),
        })
    return plots
