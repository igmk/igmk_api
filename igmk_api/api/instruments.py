"""Instrument listing, detail, and per-site deployment queries."""

from flask import send_file

from igmk_api.config import config_path, iter_configs
from igmk_api.settings import settings


def _currently_on_site(dates):
    """An instrument is still deployed when its last timespan has no end date.

    ``dates`` is a list of timespans; a length-1 entry is a start with no end,
    a length-2 entry a closed historical span.
    """
    return bool(dates) and isinstance(dates[-1], list) and len(dates[-1]) == 1


def return_instruments(siteID, showHistoric=False):
    """Map instrument ``name`` -> description/timespans for one site.

    Note this keys by the config's ``name`` field, while :func:`list_instruments`
    and :func:`instrument_details` key by filename stem; the two differ for a
    handful of instruments. See CLAUDE.md.
    """
    instruments = {}
    for _stem, config in iter_configs(settings.instruments_dir):
        name = config.get("name")
        if not name:
            continue
        for location in config.get("locations") or []:
            if not isinstance(location, dict) or location.get("site") != siteID:
                continue
            dates = location.get("dates") or []
            if showHistoric or _currently_on_site(dates):
                instruments[name] = {
                    "description": config.get("description", ""),
                    "timespans": dates,
                }
    return instruments


def return_instruments_history(siteID):
    return return_instruments(siteID, showHistoric=True)


def list_instruments():
    """Filename stems of every usable instrument config."""
    return [stem for stem, _config in iter_configs(settings.instruments_dir)]


def instrument_details(instrumentID):
    path = config_path(settings.instruments_dir, instrumentID)
    if path is None:
        return {"error": f"No instrument '{instrumentID}'"}, 404
    return send_file(path)
