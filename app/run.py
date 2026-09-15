"""Compatibility shim.

The application lives in :mod:`igmk_api.app`. This module exists so that
``run:app`` -- used by the Dockerfile CMD, by ``uvicorn run:app`` in the README,
and by any deployment runbook -- keeps working.
"""

from igmk_api.app import app  # noqa: F401
