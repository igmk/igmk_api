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
from starlette.testclient import TestClient  # noqa: E402

from igmk_api.app import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def config_root(tmp_path):
    """Point the app at a throwaway config tree for one test.

    ``settings`` is a frozen module-level singleton that handlers import by
    value, so rebinding the module attribute would not reach them; the instance
    is mutated in place and restored afterwards.
    """
    from igmk_api.settings import settings

    original = settings.config_root
    for name in ("plots", "instruments", "sites"):
        (tmp_path / name).mkdir()
    object.__setattr__(settings, "config_root", tmp_path)
    yield tmp_path
    object.__setattr__(settings, "config_root", original)
