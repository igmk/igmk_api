import datetime
import json
import os
from io import BytesIO

import requests
from connexion import FlaskApp
from pathlib import Path
from flask import redirect, send_file
from connexion.middleware import MiddlewarePosition
#from starlette.middleware.cors import CORSMiddleware
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

app = FlaskApp(__name__)
app.add_api("./openapi.yaml")

app.app.wsgi_app = ProxyFix(app.app.wsgi_app, x_proto=1, x_host=1)

CORS(app.app,
     origins=["https://browser.herz-campaigns.de"],
     supports_credentials=True)


app.app.url_map.strict_slashes = False
app.app.config['PREFERRED_URL_SCHEME'] = 'https'




if __name__ == "__main__":
    app.run(f"{Path(__file__).stem}:app",
            host="0.0.0.0",
            port=8000
            #ssl_keyfile="./localhost+1-key.pem", 
            #ssl_certfile="./localhost+1.pem"
            )

def greeter():
    return "Welcome to the API!"


def serve_favicon():
    return send_file("./static/favicon.ico")


def local_test():
    try:
        with open("/data/obs/campaigns/vital2/site/vettweiss/dial/l2/2026/05/17/vettweiss_WV-DIAL_wv_20260517.png", "rb") as f:
            f.read()
        return "ok"
    except (FileNotFoundError, IOError, OSError):
        return "not ok"


def create_map_javascript():
    js_file_path = "./static/map.js"
    if os.path.isfile(js_file_path):
        os.remove(js_file_path)
    with open(js_file_path, "a") as f:
        f.write("let map = L.map('map').setView([0, 0], 2);\n")
        f.write(
            "L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, attribution: '&copy; <a href=\"http://www.openstreetmap.org/copyright\">OpenStreetMap</a>'}).addTo(map);\n"
        )
        for filename in os.listdir("/config/sites"):
            with open(os.path.join("/config/sites", filename)) as site_file:
                site = json.load(site_file)
            list_of_keys = [
                (
                    f"<a href='https://127.0.0.1:8000/visualizations/byID/{return_plots_by_instrument(x)[0]}'>{x}</a>"
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


def return_sites():
    sites_dict = dict()
    for filename in os.listdir("/config/sites"):
        if os.path.isfile(os.path.join("/config/sites", filename)):
            with open(os.path.join("/config/sites", filename)) as site_file:
                site = json.load(site_file)
            sites_dict.update({site["siteID"]: site["siteHumanReadable"]})
    return sites_dict


def return_site_info(siteID):
    return send_file("/config/sites/" + siteID + ".json")


def return_live_data(siteID):
    with open("/config/sites.json") as sites_file:
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


def return_image(visID, dateString):
    date = datetime.datetime.strptime(dateString, "%Y%m%d")
    with open(f"/config/plots/{visID}.json") as f:
        file = json.load(f)
    image_path = date.strftime(file["path"])

    if image_path.startswith("http://") or image_path.startswith("https://"):
        response = requests.get(image_path)
        return send_file(BytesIO(response.content), mimetype="image/png")
    else:
        with open(image_path, "rb") as f:
            return send_file(BytesIO(f.read()), mimetype="image/png")


def return_current_image(visID):
    return return_image(visID, datetime.date.today().strftime("%Y%m%d"))


def return_instruments(siteID, showHistoric=False):
    instruments = dict()
    dir = "/config/instruments"
    for filename in os.listdir(dir):
        f = os.path.join(dir, filename)
        with open(f) as instrument_config_file:
            inst_file = json.load(instrument_config_file)
        for location in inst_file["locations"]:
            if location["site"] == siteID:
                instruments[inst_file["name"]] = dict(
                    description=inst_file["description"]
                )
                if len(location["dates"]) > 0:
                    if showHistoric or len(location["dates"][-1]) == 1:
                        instruments[inst_file["name"]]["timespans"] = location["dates"]
                else:
                    instruments[inst_file["name"]]["timespans"] = location["dates"]
    return instruments


def return_instruments_history(siteID):
    return return_instruments(siteID, showHistoric=True)


def list_instruments():
    dir = "/config/instruments"
    return [name[:-5] for name in os.listdir(dir)]


def instrument_details(instrumentID):
    return send_file(f"/config/instruments/{instrumentID}.json")


def return_plots_by_instrument(instrumentID):
    plots = []
    dir = "/config/plots"
    for filename in os.listdir(dir):
        f = os.path.join(dir, filename)
        with open(f) as plots_config_file:
            plots_file = json.load(plots_config_file)
        for instrument in plots_file["instruments"]:
            if instrument == instrumentID:
                plots.append(plots_file["id"])
    return plots


def search(query):
    def search_jsons(query, dir, keys):
        query = query.lower()
        results = dict()
        for path in Path(dir).glob("*.json"):
            data = json.loads(path.read_text())
            if any(query in str(data.get(key, "")).lower() for key in keys):
                file = json.loads(path.read_text())
                fileKeys = list(file.keys())
                results[file[fileKeys[0]]] = file[fileKeys[1]]
        return results
    return dict(inst=search_jsons(query, "/config/instruments", ["name", "description"]), \
        plots=search_jsons(query, "/config/plots", ["id", "description"]), \
        sites=search_jsons(query, "/config/sites", ["siteID", "siteHumanReadable"]))