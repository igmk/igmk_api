"""Greeter, favicon and the map page."""

import json
import os
from pathlib import Path

from flask import redirect, send_file

from igmk_api.api.instruments import return_instruments
from igmk_api.api.plots import return_plots_by_instrument
from igmk_api.settings import settings

# app/static, resolved absolutely so the app can start from any directory.
STATIC_DIR = Path(__file__).parents[2] / "static"


def greeter():
    return "Welcome to the API!"


def serve_favicon():
    return send_file(STATIC_DIR / "favicon.ico")


def create_map_javascript():
    js_file_path = STATIC_DIR / "map.js"
    if js_file_path.is_file():
        js_file_path.unlink()
    with js_file_path.open("a") as f:
        f.write("let map = L.map('map').setView([0, 0], 2);\n")
        f.write(
            "L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, attribution: '&copy; <a href=\"http://www.openstreetmap.org/copyright\">OpenStreetMap</a>'}).addTo(map);\n"
        )
        for filename in os.listdir(settings.sites_dir):
            with open(os.path.join(settings.sites_dir, filename)) as site_file:
                site = json.load(site_file)
            list_of_keys = [
                (
                    f"<a href='https://127.0.0.1:8000/visualizations/byID/{return_plots_by_instrument(x)[0]['id']}'>{x}</a>"
                    if len(return_plots_by_instrument(x)) > 0
                    else x
                )
                for x in list(return_instruments(site["siteID"]).keys())
            ]

            current_instruments_string = str(list_of_keys).replace("'", "\\'")[1:-1]
            #f.write(
            #    f"let {str(site["siteID"])} =L.marker([{site["lat"]},{site["lon"]}]).addTo(map).bindPopup('{site["siteHumanReadable"]} ({site["altitude"]} m ASL)<br><a href=\\'http://127.0.0.1:8000/sites/{site["siteID"]}\\'>Site details</a><br>Instruments currently on site:{current_instruments_string}');\n"
            #)


def map_redirect():
    create_map_javascript()
    return redirect("./static/map.html")
