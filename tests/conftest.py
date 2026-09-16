"""Shared fixtures.

``igmk_api.settings`` reads the environment at import time, so the config root
must be set *before* anything imports the package. pytest imports conftest
first, which makes this the right place for it.
"""

import os
import socket
from pathlib import Path

import yaml

FIXTURE_CONFIG = Path(__file__).parent / "fixtures" / "config"
# Assigned, not setdefault: a developer with IGMK_CONFIG_ROOT exported (which
# the README recommends for local runs) would otherwise silently run the whole
# suite against their real config tree.
os.environ["IGMK_CONFIG_ROOT"] = str(FIXTURE_CONFIG)

import pytest  # noqa: E402

from igmk_api.app import app  # noqa: E402
from igmk_api.config import clear_cache  # noqa: E402
from igmk_api.settings import settings  # noqa: E402

# Ids are filenames now, so these carry no id field of their own.
GOOD_SITE = {"name": "Good Site", "lat": 1, "lon": 2}
GOOD_INSTRUMENT = {
    "description": "A good instrument",
    "locations": [{"site": "good", "dates": [["2020-01-01"]]}],
}
#: A plot *group* file holding one plot, `goodplot`.
GOOD_PLOT = {
    "sites": ["good"],
    "instruments": ["goodinst"],
    "plots": {"goodplot": {"description": "A good plot", "daily": "/nonexistent/%Y%m%d.png"}},
}


def write(directory, name, content):
    """Write a config file; `content` may be a dict or raw text."""
    path = directory / name
    path.write_text(content if isinstance(content, str) else yaml.safe_dump(content))
    return path


@pytest.fixture(scope="session")
def client():
    """The app under test.

    Session-scoped, which is safe alongside the per-test ``config_root``
    fixture because handlers read ``settings.config_root`` per request.
    """
    from starlette.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """No test may touch the network.

    Upstream behaviour is exercised with `responses`, which intercepts above
    the socket layer. Without this guard a fixture pointing at
    example.invalid silently performs a real DNS lookup on every run.
    """

    def blocked(*args, **kwargs):
        raise AssertionError("test attempted a real network connection")

    monkeypatch.setattr(socket, "getaddrinfo", blocked)


@pytest.fixture(autouse=True)
def _isolate_config_cache():
    """Configs are cached in-process; don't let one test's tree reach another."""
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def config_root(tmp_path):
    """Point the app at a throwaway config tree for one test."""
    original = settings.config_root
    for name in ("plots", "instruments", "sites"):
        (tmp_path / name).mkdir()
    settings.config_root = tmp_path
    yield tmp_path
    settings.config_root = original


@pytest.fixture
def populated(config_root):
    """One good config in each directory, ready for junk to be added."""
    write(config_root / "sites", "good.yaml", GOOD_SITE)
    write(config_root / "instruments", "goodinst.yaml", GOOD_INSTRUMENT)
    write(config_root / "plots", "goodplot.yaml", GOOD_PLOT)
    return config_root
