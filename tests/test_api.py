"""Frontend contract lock.

These pin the response *shapes* that browser.herz-campaigns.de consumes. The
deployed client is mirrored at ``docs/dataBrowser.reference.js``; each test names
the line that consumes the response. If a refactor changes one of
these shapes, it breaks the browser -- so it should break the build first.
"""

import pytest


def test_greeter(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.text == "Welcome to the API!"


def test_sites_is_id_to_label_map(client):
    """dataBrowser.reference.js:227 -- Object.entries(data) -> tiles of id/label."""
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
    """dataBrowser.reference.js:336 -- merged with Object.assign, keys become tiles.

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


def test_instrument_list_and_site_instruments_share_one_id_space(client):
    """There used to be two: this route keyed by filename stem while
    /sites/{id}/instruments keyed by a `name` field, and they disagreed for
    _halo_rpg / joyrad_10 / raman_lidar. The `name` field is gone -- an
    instrument's id is its filename -- so the two agree by construction, and an
    id from one route is guaranteed to work on the other."""
    r = client.get("/instruments")
    assert r.status_code == 200
    assert sorted(r.json()) == ["tstlidar", "tstrad", "tstsonde"]
    assert set(client.get("/sites/tst/instruments/history").json()) <= set(r.json())


def test_instrument_detail(client):
    r = client.get("/instruments/tstrad")
    assert r.status_code == 200
    assert r.json()["name"] == "tstrad"


def test_plots_by_instrument_shape(client):
    """docs/dataBrowser.reference.js:351 -- documented as `[{id, granularities}]`.

    The handler returns a *list* and the mirrored client consumes it as one:
    :362-363 use `data.filter(p => ...)` and :651 guards with
    `Array.isArray(plots)`. An earlier revision of this docstring warned that
    the client used `Object.entries` here and built
    '/byID/[object Object]/<ymd>'; that mirror has since been refreshed, so the
    warning was stale, not a live defect.
    """
    r = client.get("/visualizations/byInstrument/tstrad")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    by_id = {p["id"]: p for p in data}
    assert set(by_id) == {"tstrad_legacy", "tstrad_granular", "tst_combined"}
    # A legacy `path` config advertises daily only.
    assert by_id["tstrad_legacy"]["granularities"] == ["daily"]
    assert by_id["tstrad_legacy"]["multi"] is False
    # A `paths` config advertises exactly the granularities it declares,
    # in GRANULARITY_FORMATS order.
    assert by_id["tstrad_granular"]["granularities"] == [
        "daily", "monthly", "seasonal", "yearly",
    ]


def test_plot_can_be_driven_by_several_instruments(client):
    """A derived product has no single owning instrument, so it has to appear
    under each one that feeds it -- which is why plot group files express
    `instruments` as an overridable list rather than owning their plots."""
    for instrument in ("tstrad", "tstlidar"):
        ids = [p["id"] for p in client.get(f"/visualizations/byInstrument/{instrument}").json()]
        assert "tst_combined" in ids, instrument


def test_plots_by_instrument_flags_multi(client):
    r = client.get("/visualizations/byInstrument/tstsonde")
    assert r.status_code == 200
    (plot,) = r.json()
    assert plot["id"] == "tstsonde_skewt"
    assert plot["multi"] is True


def test_search_shape(client):
    """dataBrowser.reference.js:666 -- reads data.sites, data.inst, data.plots."""
    r = client.get("/search/test")
    assert r.status_code == 200
    data = r.json()
    assert set(data) == {"inst", "plots", "sites"}
    assert all(isinstance(v, dict) for v in data.values())
    assert data["sites"]["tst"] == "Test Site"
    assert data["inst"]["tstrad"] == "Test Radiometer"


def test_search_plot_values_are_descriptions(client):
    """search() used to key results by positional JSON key order
    (``file[keys[0]] -> file[keys[1]]``). Plot configs start ("id", "sites"),
    so plot values were the *site list*, and the client adapted with
    ``Array.isArray(value) ? value.join(', ') : value``
    (docs/dataBrowser.reference.js:1088). Keys are now named explicitly, so a
    plot's value is its description; the client's Array check still tolerates
    both, which is what made the change safe to ship.
    """
    data = client.get("/search/legacy").json()
    assert data["plots"] == {"tstrad_legacy": "Legacy single-path plot"}


def test_search_is_case_insensitive(client):
    """openapi.yaml promises `matched case-insensitively`."""
    assert client.get("/search/TEST").json() == client.get("/search/test").json()
    assert client.get("/search/TEST").json()["sites"]["tst"] == "Test Site"


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


def test_multi_plot_rejects_direct_image_request(client):
    r = client.get("/visualizations/byID/tstsonde_skewt/daily/20250101")
    assert r.status_code == 400


def test_plot_error_bodies_are_json(client):
    """The plot exists but declares no monthly path -- and the error body arrives.

    openapi.yaml used to declare only ``image/png`` for these routes, so
    Connexion serialised the dict against that content type and the client
    received the literal string "error"; only the status code was usable.
    """
    r = client.get("/visualizations/byID/tstrad_legacy/monthly/202501")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")
    assert "error" in r.json()
