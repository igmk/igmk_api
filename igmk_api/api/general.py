"""Greeter and favicon."""

from pathlib import Path

from flask import send_file

# static/ at the repo root, resolved absolutely so the app can start from
# any directory.
STATIC_DIR = Path(__file__).parents[2] / "static"


def greeter():
    return "Welcome to the API!"


def serve_favicon():
    return send_file(STATIC_DIR / "favicon.ico", mimetype="image/vnd.microsoft.icon")
