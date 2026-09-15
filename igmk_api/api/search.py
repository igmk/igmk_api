"""Free-text search across instruments, plots and sites."""

from pathlib import Path

from igmk_api.config import load_configs
from igmk_api.settings import settings


def _matching(directory: Path, query: str, id_key: str, label_key: str) -> dict[str, str]:
    """Return ``{id: label}`` for configs whose id or label contains *query*."""
    results = {}
    for _stem, config in load_configs(directory):
        identifier = config.get(id_key)
        label = config.get(label_key, "")
        if identifier and query in f"{identifier} {label}".lower():
            results[identifier] = label
    return results


def search(query: str) -> dict[str, dict[str, str]]:
    query = query.lower()
    return {
        "inst": _matching(settings.instruments_dir, query, "name", "description"),
        "plots": _matching(settings.plots_dir, query, "id", "description"),
        "sites": _matching(settings.sites_dir, query, "siteID", "siteHumanReadable"),
    }
