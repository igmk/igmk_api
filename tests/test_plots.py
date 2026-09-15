"""Plot image serving: multi-item dates and upstream failure modes.

These routes are what the browser actually loads (docs/dataBrowser.reference.js
:36, :43, :46). Upstream responses are mocked, so the suite stays hermetic and
every failure branch is reachable.
"""

import pytest
import requests
import responses
from conftest import write

REMOTE = "https://plots.example.test/%Y/%Y%m%d.png"
REMOTE_20250101 = "https://plots.example.test/2025/20250101.png"


@pytest.fixture
def plots(config_root):
    """A remote plot, a local multi-item plot, and a remote multi-item plot."""
    items = config_root / "items"
    items.mkdir()
    write(config_root / "plots", "remote.json", {"id": "remote", "path": REMOTE})
    write(config_root / "plots", "multi.json", {
        "id": "multi",
        "multi": True,
        "paths": {"daily": f"{items}/%Y%m%d"},
        "pattern": "rs_%Y%m%d*_skewt.png",
    })
    write(config_root / "plots", "multiremote.json", {
        "id": "multiremote", "multi": True, "paths": {"daily": REMOTE},
    })
    return items


def add_day(items, ymd, names):
    day = items / ymd
    day.mkdir(exist_ok=True)
    for name in names:
        (day / name).write_bytes(b"\x89PNG")
    return day


# --- multi-item listing and retrieval ---------------------------------------


def test_item_count_for_a_day(client, plots):
    add_day(plots, "20250101", ["rs_20250101_06_skewt.png", "rs_20250101_00_skewt.png"])
    r = client.get("/visualizations/byID/multi/daily/20250101/items")
    assert r.status_code == 200
    assert r.json() == {"count": 2}


def test_item_count_ignores_files_not_matching_the_pattern(client, plots):
    add_day(plots, "20250101", ["rs_20250101_00_skewt.png", "notes.txt", "other.png"])
    assert client.get("/visualizations/byID/multi/daily/20250101/items").json() == {"count": 1}


def test_item_count_is_zero_for_a_day_with_no_directory(client, plots):
    """An empty day is not an error."""
    r = client.get("/visualizations/byID/multi/daily/20250101/items")
    assert r.status_code == 200
    assert r.json() == {"count": 0}


def test_items_are_served_in_sorted_order(client, plots):
    add_day(plots, "20250101", ["rs_20250101_12_skewt.png", "rs_20250101_00_skewt.png"])
    for index in (0, 1):
        r = client.get(f"/visualizations/byID/multi/daily/20250101/items/{index}")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
    # index 0 is the 00 sounding, because listing is sorted by filename
    assert client.get("/visualizations/byID/multi/daily/20250101/items/0").content == b"\x89PNG"


def test_item_index_past_the_end_is_404(client, plots):
    add_day(plots, "20250101", ["rs_20250101_00_skewt.png"])
    r = client.get("/visualizations/byID/multi/daily/20250101/items/5")
    assert r.status_code == 404
    assert "1 item(s)" in r.json()["error"]


@pytest.mark.parametrize("url", [
    "/visualizations/byID/multiremote/daily/20250101/items",
    "/visualizations/byID/multiremote/daily/20250101/items/0",
])
def test_listing_items_of_a_remote_plot_is_501(client, plots, url):
    assert client.get(url).status_code == 501


def test_items_route_rejects_a_non_multi_plot(client, plots):
    assert client.get("/visualizations/byID/remote/daily/20250101/items").status_code == 400


# --- remote image fetching --------------------------------------------------


@responses.activate
def test_remote_image_is_served(client, plots):
    responses.add(responses.GET, REMOTE_20250101, body=b"\x89PNG", status=200)
    r = client.get("/visualizations/byID/remote/daily/20250101")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content == b"\x89PNG"


@responses.activate
def test_upstream_404_becomes_404(client, plots):
    responses.add(responses.GET, REMOTE_20250101, status=404)
    r = client.get("/visualizations/byID/remote/daily/20250101")
    assert r.status_code == 404
    assert "error" in r.json()


@responses.activate
def test_upstream_500_becomes_502(client, plots):
    responses.add(responses.GET, REMOTE_20250101, status=500)
    assert client.get("/visualizations/byID/remote/daily/20250101").status_code == 502


@pytest.mark.parametrize("failure", [
    requests.exceptions.ConnectionError("connection reset"),
    requests.exceptions.ReadTimeout("too slow"),
])
@responses.activate
def test_upstream_transport_failure_becomes_502(client, plots, failure):
    """A timeout used to be un-catchable: `except ReadTimeout():` instantiated
    the class, raising TypeError instead of catching."""
    responses.add(responses.GET, REMOTE_20250101, body=failure)
    r = client.get("/visualizations/byID/remote/daily/20250101")
    assert r.status_code == 502
    assert r.json()["error"]


@responses.activate
def test_current_image_route_uses_today(client, plots):
    """/visualizations/byID/{visID} with no date resolves to today."""
    import datetime

    today = datetime.date.today()
    responses.add(
        responses.GET,
        today.strftime("https://plots.example.test/%Y/%Y%m%d.png"),
        body=b"\x89PNG",
        status=200,
    )
    r = client.get("/visualizations/byID/remote")
    assert r.status_code == 200
    assert r.content == b"\x89PNG"
