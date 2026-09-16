"""Free-text search across instruments, plots and sites."""

from igmk_api.index import instrument_index, plot_index, site_index


def _matching(records: dict[str, dict], query: str, label_key: str) -> dict[str, str]:
    """Return ``{id: label}`` for records whose id or label contains *query*."""
    return {
        identifier: record[label_key]
        for identifier, record in records.items()
        if query in f"{identifier} {record[label_key]}".lower()
    }


def search(query: str) -> dict[str, dict[str, str]]:
    query = query.lower()
    return {
        "inst": _matching(instrument_index(), query, "description"),
        "plots": _matching(plot_index(), query, "description"),
        "sites": _matching(site_index(), query, "name"),
    }
