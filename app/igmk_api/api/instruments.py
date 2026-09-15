"""Instrument listing, detail, and per-site deployment queries."""

import json
import os

from flask import send_file

from igmk_api.settings import settings


def return_instruments(siteID, showHistoric=False):
    instruments = dict()
    dir = str(settings.instruments_dir)
    for filename in os.listdir(dir):
        f = os.path.join(dir, filename)
        with open(f) as instrument_config_file:
            inst_file = json.load(instrument_config_file)
        for location in inst_file["locations"]:
            if location["site"] != siteID:
                continue
            dates = location["dates"]
            currently_on_site = len(dates) > 0 and len(dates[-1]) == 1
            if showHistoric or currently_on_site:
                instruments[inst_file["name"]] = dict(
                    description=inst_file["description"],
                    timespans=dates,
                )
    return instruments


def return_instruments_history(siteID):
    return return_instruments(siteID, showHistoric=True)


def list_instruments():
    dir = str(settings.instruments_dir)
    return [name[:-5] for name in os.listdir(dir)]


def instrument_details(instrumentID):
    return send_file(settings.instruments_dir / f"{instrumentID}.json")
