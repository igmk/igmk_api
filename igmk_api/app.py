"""Application factory and ASGI entrypoint.

This is the only place routes get wired. Handlers live in :mod:`igmk_api.api`
and are bound to paths by ``operationId`` in ``openapi.yaml``; the two must stay
in sync or a route 404s / the app fails to start. ``tests/test_spec.py``
enforces that.
"""

from pathlib import Path

from connexion import FlaskApp
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

SPEC_PATH = Path(__file__).with_name("openapi.yaml")

CORS_ORIGINS = ["https://browser.herz-campaigns.de"]


def create_app() -> FlaskApp:
    """Build the Connexion application."""
    connexion_app = FlaskApp(__name__, specification_dir=str(SPEC_PATH.parent))
    # Absolute, so the app can be started from any working directory rather
    # than only from app/ (the Dockerfile's WORKDIR).
    connexion_app.add_api(SPEC_PATH)

    flask_app = connexion_app.app
    flask_app.wsgi_app = ProxyFix(flask_app.wsgi_app, x_proto=1, x_host=1)
    flask_app.url_map.strict_slashes = False
    flask_app.config["PREFERRED_URL_SCHEME"] = "https"

    CORS(flask_app, origins=CORS_ORIGINS, supports_credentials=True)

    return connexion_app


app = create_app()
