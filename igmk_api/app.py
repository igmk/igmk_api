"""Application factory and ASGI entrypoint.

This is the only place routes get wired. Handlers live in :mod:`igmk_api.api`
and are bound to paths by ``operationId`` in ``openapi.yaml``; the two must stay
in sync or a route 404s / the app fails to start. ``tests/test_spec.py``
enforces that.
"""

from pathlib import Path

from connexion import FlaskApp
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix

from igmk_api.settings import settings

#: Absolute, so the app can be started from any working directory.
SPEC_PATH = Path(__file__).with_name("openapi.yaml")


def create_app() -> FlaskApp:
    """Build the Connexion application."""
    connexion_app = FlaskApp(__name__, specification_dir=str(SPEC_PATH.parent))
    connexion_app.add_api(SPEC_PATH)

    # CORS goes on the ASGI stack, outside the exception middleware, so that
    # Connexion's own routing 404s and validation 400s carry the headers too.
    # On the Flask app it would only cover responses that reach Flask, and the
    # browser would see those errors as opaque failures.
    connexion_app.add_middleware(
        CORSMiddleware,
        position=MiddlewarePosition.BEFORE_EXCEPTION,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    flask_app = connexion_app.app
    flask_app.wsgi_app = ProxyFix(flask_app.wsgi_app, x_proto=1, x_host=1)
    flask_app.config["PREFERRED_URL_SCHEME"] = "https"

    return connexion_app


app = create_app()
