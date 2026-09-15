"""Site listing, detail and live-data proxy."""

import json
import os

import requests
from flask import send_file

from igmk_api.settings import settings


def return_sites():
    sites_dict = dict()
    for filename in os.listdir(settings.sites_dir):
        if os.path.isfile(os.path.join(settings.sites_dir, filename)):
            with open(os.path.join(settings.sites_dir, filename)) as site_file:
                site = json.load(site_file)
            sites_dict.update({site["siteID"]: site["siteHumanReadable"]})
    return sites_dict


def return_site_info(siteID):
    return send_file(settings.sites_dir / (siteID + ".json"))


def return_live_data(siteID):
    with open(settings.config_root / "sites.json") as sites_file:
        sites = json.load(sites_file)
    if siteID not in sites.keys():
        return {}, 400
    try:
        response = requests.get(
            sites[siteID]["liveDataPath"],
            timeout=60,
        )
        if response.status_code == 200:
            data = json.loads(response.text)
            return data, 200
        else:
            return {}, 503
    # Handle timeout
    except requests.exceptions.ReadTimeout():
        return {}, 503
    # Handle empty strings as Not Implemented
    except requests.exceptions.MissingSchema():
        return {}, 501
