"""Instrument listing, detail, and per-site deployment queries."""

from flask import send_file

from igmk_api.config import config_path, load_configs
from igmk_api.settings import settings


def _currently_on_site(dates: list) -> bool:
    """Still deployed when the last timespan is a start with no end date."""
    return bool(dates) and isinstance(dates[-1], list) and len(dates[-1]) == 1


def _instruments_at_site(siteID: str, *, include_historic: bool) -> dict[str, dict]:
    """Map instrument ``name`` -> description/timespans for one site.

    Keys by the config's ``name`` field, while :func:`instruments` and
    :func:`instrument_details` key by filename stem; the two differ for a
    handful of instruments. See CLAUDE.md.
    """
    instruments = {}
    for _stem, config in load_configs(settings.instruments_dir):
        name = config.get("name")
        if not name:
            continue
        for location in config.get("locations") or []:
            if not isinstance(location, dict) or location.get("site") != siteID:
                continue
            dates = location.get("dates") or []
            if include_historic or _currently_on_site(dates):
                instruments[name] = {
                    "description": config.get("description", ""),
                    "timespans": dates,
                }
    return instruments


def site_instruments(siteID: str) -> dict[str, dict]:
    return _instruments_at_site(siteID, include_historic=False)


def site_instruments_history(siteID: str) -> dict[str, dict]:
    return _instruments_at_site(siteID, include_historic=True)


def instruments() -> list[str]:
    """Filename stems of every usable instrument config."""
    return [stem for stem, _config in load_configs(settings.instruments_dir)]


def instrument_details(instrumentID: str):
    path = config_path(settings.instruments_dir, instrumentID)
    if path is None:
        return {"error": f"No instrument '{instrumentID}'"}, 404
    return send_file(path)
