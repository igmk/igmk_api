"""Site listing, detail and live-data proxy."""

import requests
from flask import send_file

from igmk_api.config import config_path, iter_configs, read_config
from igmk_api.settings import settings

#: (connect, read) seconds. The live-data feeds are third-party hosts, so a
#: hang there must not pin a worker for the pool's lifetime.
LIVE_DATA_TIMEOUT = (5, 15)


def return_sites():
    """Map siteID -> human-readable label."""
    sites = {}
    for _stem, config in iter_configs(settings.sites_dir):
        site_id = config.get("siteID")
        label = config.get("siteHumanReadable")
        if site_id and label:
            sites[site_id] = label
    return sites


def return_site_info(siteID):
    path = config_path(settings.sites_dir, siteID)
    if path is None:
        return {"error": f"No site '{siteID}'"}, 404
    return send_file(path)


def return_live_data(siteID):
    """Proxy the site's upstream live-data feed."""
    site = read_config(settings.sites_dir, siteID)
    if site is None:
        return {"error": f"No site '{siteID}'"}, 404
    url = site.get("liveDataPath")
    if not url:
        return {"error": f"Site '{siteID}' has no live data feed"}, 501
    try:
        response = requests.get(url, timeout=LIVE_DATA_TIMEOUT)
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
