"""Turning config files into the flat records the handlers serve.

The config *file* schema and the API *wire* schema are deliberately different
things. Files are optimised for a scientist with a text editor: plots are
grouped into one file per site/instrument combination, sharing a ``base`` path
and a default instrument list, and the common case is a single line. Handlers
want one flat record per id. This module is the only place that maps between
them, which is what lets the file format change without touching a response
body.

Like :mod:`igmk_api.config`, nothing here raises on bad input: a malformed entry
is logged and skipped so the rest of the file still serves.
"""

import logging

from igmk_api.config import load_configs
from igmk_api.settings import settings

log = logging.getLogger(__name__)

#: Granularity -> the exact strftime format its ``dateString`` must match.
#: Seasonal is addressed by the start month of the season (202606 = JJA).
GRANULARITY_FORMATS = {
    "daily": "%Y%m%d",
    "monthly": "%Y%m",
    "seasonal": "%Y%m",
    "yearly": "%Y",
}

#: Keys allowed on a single plot entry. Anything else is a typo -- most likely a
#: misspelled granularity, which would otherwise silently drop the image.
PLOT_KEYS = {"description", "sites", "instruments", "multi", "pattern", *GRANULARITY_FORMATS}

#: Keys allowed at the top of a plot group file.
GROUP_KEYS = {"sites", "instruments", "base", "plots"}


def as_list(value) -> list[str]:
    """Accept either ``sites: jue`` or ``sites: [jue, aac]``."""
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str) and v]
    return []


def is_remote(path: str) -> bool:
    return path.startswith(("http://", "https://"))


def join_base(base: str, path: str) -> str:
    """Resolve *path* against *base*, unless *path* is already absolute."""
    if not base or path.startswith("/") or is_remote(path):
        return path
    return base + path if base.endswith("/") else f"{base}/{path}"


def _expand_group(stem: str, config: dict, index: dict[str, dict]) -> None:
    """Expand one plot group file into *index*, keyed by plot id."""
    plots = config.get("plots")
    if not isinstance(plots, dict):
        log.warning("skipping plot group %r: no 'plots' mapping", stem)
        return
    if unknown := set(config) - GROUP_KEYS:
        log.warning("plot group %r has unknown top-level keys: %s", stem, sorted(unknown))

    base = config.get("base") if isinstance(config.get("base"), str) else ""
    group_sites = as_list(config.get("sites"))
    group_instruments = as_list(config.get("instruments"))

    for plot_id, body in plots.items():
        if not isinstance(plot_id, str) or not plot_id:
            log.warning("skipping plot in group %r: id %r is not a usable string", stem, plot_id)
            continue
        # Shorthand: "<id>: <daily path>", which is most of the tree.
        if isinstance(body, str):
            body = {"daily": body}
        if not isinstance(body, dict):
            log.warning("skipping plot %r in group %r: entry is not a mapping", plot_id, stem)
            continue
        if unknown := set(body) - PLOT_KEYS:
            log.warning("plot %r in group %r has unknown keys: %s", plot_id, stem, sorted(unknown))

        paths = {
            gran: join_base(base, template)
            for gran in GRANULARITY_FORMATS
            if isinstance(template := body.get(gran), str) and template
        }
        if not paths:
            log.warning("skipping plot %r in group %r: declares no image paths", plot_id, stem)
            continue
        if plot_id in index:
            log.warning("duplicate plot id %r (group %r); keeping the first", plot_id, stem)
            continue

        pattern = body.get("pattern")
        index[plot_id] = {
            "id": plot_id,
            "sites": as_list(body["sites"]) if "sites" in body else group_sites,
            "instruments": (
                as_list(body["instruments"]) if "instruments" in body else group_instruments
            ),
            "description": body.get("description") or "",
            "multi": bool(body.get("multi")),
            "pattern": pattern if isinstance(pattern, str) else None,
            "paths": paths,
        }


def plot_index() -> dict[str, dict]:
    """Plot id -> ``{id, sites, instruments, description, multi, pattern, paths}``.

    ``paths`` is granularity -> a fully resolved strftime template: ``base`` is
    already applied, so a handler never has to know groups exist.

    Ordered by plot id, so which group file a plot happens to live in affects
    nothing an ordered response exposes -- notably the tile order of
    ``/visualizations/byInstrument``.

    Rebuilt per call rather than cached: it is a few hundred dict operations
    over data :mod:`igmk_api.config` has already parsed and cached, and skipping
    the cache is what keeps "edit a file, see it on the next request" true.
    """
    index: dict[str, dict] = {}
    for stem, config in load_configs(settings.plots_dir):
        _expand_group(stem, config, index)
    return dict(sorted(index.items()))


def granularities(record: dict) -> list[str]:
    """A plot's granularities, always in daily/monthly/seasonal/yearly order."""
    return [g for g in GRANULARITY_FORMATS if g in record["paths"]]


def instrument_index() -> dict[str, dict]:
    """Instrument id (the filename stem) -> its config, with ``id`` filled in."""
    index = {}
    for stem, config in load_configs(settings.instruments_dir):
        locations = [loc for loc in (config.get("locations") or []) if isinstance(loc, dict)]
        index[stem] = {
            "id": stem,
            "description": config.get("description") or "",
            "wiki": config.get("wiki") or "",
            "locations": locations,
        }
    return index


def site_index() -> dict[str, dict]:
    """Site id (the filename stem) -> its config, with ``id`` filled in."""
    index = {}
    for stem, config in load_configs(settings.sites_dir):
        index[stem] = {
            "id": stem,
            "name": config.get("name") or "",
            "description": config.get("description") or "",
            "live_data": config.get("live_data") or "",
            "lat": config.get("lat"),
            "lon": config.get("lon"),
            "altitude": config.get("altitude"),
        }
    return index
