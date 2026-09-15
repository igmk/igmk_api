"""Shared fixtures.

``igmk_api.settings`` reads the environment at import time, so the config root
must be set *before* anything imports the package. pytest imports conftest
first, which makes this the right place for it.
"""

import os
from pathlib import Path

FIXTURE_CONFIG = Path(__file__).parent / "fixtures" / "config"
os.environ.setdefault("IGMK_CONFIG_ROOT", str(FIXTURE_CONFIG))

import pytest  # noqa: E402
from igmk_api.app import app  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
