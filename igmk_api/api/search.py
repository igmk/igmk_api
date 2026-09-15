"""Free-text search across instruments, plots and sites."""

from igmk_api.config import iter_configs
from igmk_api.settings import settings


def _matching(directory, query, match_keys, id_key, label_key):
    """Return ``{id: label}`` for configs whose *match_keys* contain *query*.

    The keys are named explicitly. This used to read ``file[keys[0]]`` ->
    ``file[keys[1]]``, i.e. by JSON key *insertion order*, so reordering keys in
    a config silently changed the API response.
    """
    results = {}
    for _stem, config in iter_configs(directory):
        if not any(query in str(config.get(key, "")).lower() for key in match_keys):
            continue
        identifier = config.get(id_key)
        if identifier:
            results[identifier] = config.get(label_key, "")
    return results


def search(query):
    query = query.lower()
    return {
        "inst": _matching(
            settings.instruments_dir, query, ("name", "description"), "name", "description"
        ),
        "plots": _matching(
            settings.plots_dir, query, ("id", "description"), "id", "description"
        ),
        "sites": _matching(
            settings.sites_dir, query, ("siteID", "siteHumanReadable"),
            "siteID", "siteHumanReadable",
        ),
    }
