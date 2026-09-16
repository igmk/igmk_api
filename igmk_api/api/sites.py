"""Site listing, detail and live-data proxy."""

import requests

from igmk_api.index import site_index

#: (connect, read) seconds. Live-data feeds are third-party hosts, so a hang
#: there must not pin a worker.
LIVE_DATA_TIMEOUT = (5, 15)

_http = requests.Session()


def _wire(record: dict) -> dict:
    """Config record -> the response body clients have always received.

    The file calls these ``name`` and ``live_data``; the API has called them
    ``siteHumanReadable`` and ``liveDataPath`` since before the config was
    reshaped, and renaming them would be a breaking change for no gain.
    """
    return {
        "siteID": record["id"],
        "siteHumanReadable": record["name"],
        "description": record["description"],
        "liveDataPath": record["live_data"],
        "lat": record["lat"],
        "lon": record["lon"],
        "altitude": record["altitude"],
    }


def sites() -> dict[str, str]:
    """Map siteID -> human-readable label."""
    return {site_id: rec["name"] for site_id, rec in site_index().items() if rec["name"]}


def site_info(siteID: str):
    record = site_index().get(siteID)
    if record is None:
        return {"error": f"No site '{siteID}'"}, 404
    return _wire(record), 200


def site_live_data(siteID: str):
    """Proxy the site's upstream live-data feed."""
    record = site_index().get(siteID)
    if record is None:
        return {"error": f"No site '{siteID}'"}, 404
    url = record["live_data"]
    if not url:
        return {"error": f"Site '{siteID}' has no live data feed"}, 501
    try:
        response = _http.get(url, timeout=LIVE_DATA_TIMEOUT)
    except requests.exceptions.MissingSchema:
        return {"error": f"Site '{siteID}' has a malformed live data URL"}, 501
    except requests.RequestException:
        return {"error": "Live data upstream is unavailable"}, 503
    if not response.ok:
        return {"error": "Live data upstream is unavailable"}, 503
    try:
        return response.json(), 200
    except ValueError:
        return {"error": "Live data upstream returned invalid JSON"}, 502
