"""Frontend contract lock.

These pin the response *shapes* that browser.herz-campaigns.de consumes. The
deployed client is mirrored at ``dataBrowser.js.temp`` in the repo root; each
test names the line that consumes the response. If a refactor changes one of
these shapes, it breaks the browser -- so it should break the build first.
"""

import pytest


def test_greeter(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.text == "Welcome to the API!"


def test_sites_is_id_to_label_map(client):
    """dataBrowser.js.temp:227 -- Object.entries(data) -> tiles of id/label."""
    r = client.get("/sites")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in data.items())
    assert data["tst"] == "Test Site"


def test_site_detail(client):
    r = client.get("/sites/tst")
    assert r.status_code == 200
    data = r.json()
    assert data["siteID"] == "tst"
    for key in ("siteHumanReadable", "lat", "lon", "altitude"):
        assert key in data


def test_site_instruments_shape(client):
    """dataBrowser.js.temp:336 -- merged with Object.assign, keys become tiles.

    Only instruments *currently* on site: the convention is that the last
    `dates` entry having length 1 (a start with no end) means still deployed.
    """
    r = client.get("/sites/tst/instruments")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert set(data) == {"tstrad", "tstsonde"}, "tstlidar left the site in 2019"
    assert data["tstrad"]["description"] == "Test Radiometer"
    assert data["tstrad"]["timespans"] == [["2020-01-01"]]


def test_site_instruments_history_includes_departed(client):
    r = client.get("/sites/tst/instruments/history")
    assert r.status_code == 200
    assert set(r.json()) == {"tstrad", "tstlidar", "tstsonde"}


def test_instrument_list_is_filename_stems(client):
    """Note the two identifiers in play: this route keys by *filename stem*
    while /sites/{id}/instruments keys by the `name` field. tstsonde_v2.json
    has name 'tstsonde', mirroring _halo_rpg / raman_lidar in the real config."""
    r = client.get("/instruments")
    assert r.status_code == 200
    assert sorted(r.json()) == ["tstlidar", "tstrad", "tstsonde_v2"]


def test_instrument_detail(client):
    r = client.get("/instruments/tstrad")
    assert r.status_code == 200
    assert r.json()["name"] == "tstrad"


def test_plots_by_instrument_shape(client):
    """dataBrowser.js.temp:346 -> populateGrid -> :247 Object.entries(data).

    NOTE: the handler returns a *list*, so Object.entries() yields
    ["0", {...}] and dataBrowser.js.temp:299 builds
    '/byID/[object Object]/<ymd>'. Either the deployed JS is newer than the
    mirrored copy, or instrument->plot navigation is broken in production.
    This test pins the current shape so it cannot drift further unnoticed;
    it should be revisited alongside the frontend.
    """
    r = client.get("/visualizations/byInstrument/tstrad")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    by_id = {p["id"]: p for p in data}
    assert set(by_id) == {"tstrad_legacy", "tstrad_granular"}
    # A legacy `path` config advertises daily only.
    assert by_id["tstrad_legacy"]["granularities"] == ["daily"]
    assert by_id["tstrad_legacy"]["multi"] is False
    # A `paths` config advertises exactly the granularities it declares,
    # in GRANULARITY_FORMATS order.
    assert by_id["tstrad_granular"]["granularities"] == [
        "daily", "monthly", "seasonal", "yearly",
    ]


def test_plots_by_instrument_flags_multi(client):
    r = client.get("/visualizations/byInstrument/tstsonde")
    assert r.status_code == 200
    (plot,) = r.json()
    assert plot["id"] == "tstsonde_skewt"
    assert plot["multi"] is True


def test_search_shape(client):
    """dataBrowser.js.temp:666 -- reads data.sites, data.inst, data.plots."""
    r = client.get("/search/test")
    assert r.status_code == 200
    data = r.json()
    assert set(data) == {"inst", "plots", "sites"}
    assert all(isinstance(v, dict) for v in data.values())
    assert data["sites"]["tst"] == "Test Site"
    assert data["inst"]["tstrad"] == "Test Radiometer"


def test_search_plot_values_are_site_lists(client):
    """Documents a real quirk rather than endorsing it.

    search() keys results by positional JSON key order
    (``file[keys[0]] -> file[keys[1]]``). Plot configs start ("id", "sites"),
    so plot values are the *site list*, not the description -- and
    dataBrowser.js.temp:690 has adapted, doing
    ``Array.isArray(value) ? value.join(', ') : value``.
    Scheduled to change in the bug-fix round; frontend needs a heads-up.
    """
    data = client.get("/search/legacy").json()
    assert data["plots"] == {"tstrad_legacy": ["tst"]}


@pytest.mark.parametrize(
    "granularity,date_string,expected_status",
    [
        ("daily", "20250101", None),     # valid -> not a validation rejection
        ("monthly", "202501", None),
        ("yearly", "2025", None),
        ("daily", "2025-01-01", 400),    # wrong date format for granularity
        ("hourly", "20250101", 400),     # unknown granularity
    ],
)
def test_plot_date_validation(client, granularity, date_string, expected_status):
    r = client.get(f"/visualizations/byID/tstrad_granular/{granularity}/{date_string}")
    if expected_status is None:
        # The fixture points at example.invalid, so a 200 is impossible here;
        # what matters is that validation let the request through.
        assert r.status_code != 400
    else:
        assert r.status_code == expected_status


def test_unsupported_granularity_for_plot(client):
    """The plot exists but declares no monthly path."""
    r = client.get("/visualizations/byID/tstrad_legacy/monthly/202501")
    assert r.status_code == 404


def test_multi_plot_rejects_direct_image_request(client):
    r = client.get("/visualizations/byID/tstsonde_skewt/daily/20250101")
    assert r.status_code == 400


def test_plot_error_bodies_are_not_json_yet(client):
    """Pins a known defect so the eventual fix is a deliberate, visible change.

    The plot handlers build careful ``{"error": ...}`` bodies, but openapi.yaml
    declares only ``image/png`` for these routes, so Connexion serialises the
    dict against that content type and the client receives the literal string
    "error" as image/png. Only the status code is usable today.

    Verified identical on the pre-refactor run.py, so this is long-standing
    behaviour, not refactor fallout. It resolves once the spec declares JSON
    error responses in the spec-repair round.
    """
    r = client.get("/visualizations/byID/tstrad_legacy/monthly/202501")
    assert r.status_code == 404
    assert r.headers["content-type"] == "image/png"
    assert r.text == "error"
