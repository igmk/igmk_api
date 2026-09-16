"""Instrument listing, detail, and per-site deployment queries."""

from igmk_api.index import instrument_index


def _currently_on_site(dates: list) -> bool:
    """Still deployed when the last timespan is a start with no end date."""
    return bool(dates) and isinstance(dates[-1], list) and len(dates[-1]) == 1


def _instruments_at_site(siteID: str, *, include_historic: bool) -> dict[str, dict]:
    """Map instrument id -> description/timespans for one site."""
    instruments = {}
    for instrument_id, record in instrument_index().items():
        for location in record["locations"]:
            if location.get("site") != siteID:
                continue
            dates = location.get("dates") or []
            if include_historic or _currently_on_site(dates):
                instruments[instrument_id] = {
                    "description": record["description"],
                    "timespans": dates,
                }
    return instruments


def site_instruments(siteID: str) -> dict[str, dict]:
    return _instruments_at_site(siteID, include_historic=False)


def site_instruments_history(siteID: str) -> dict[str, dict]:
    return _instruments_at_site(siteID, include_historic=True)


def instruments() -> list[str]:
    """Every instrument id, which is its filename stem."""
    return list(instrument_index())


def instrument_details(instrumentID: str):
    record = instrument_index().get(instrumentID)
    if record is None:
        return {"error": f"No instrument '{instrumentID}'"}, 404
    return {
        # `name` is the wire spelling of what the file now expresses as its
        # filename; one identifier, two names for it.
        "name": record["id"],
        "description": record["description"],
        "locations": record["locations"],
        "wiki": record["wiki"],
    }, 200
