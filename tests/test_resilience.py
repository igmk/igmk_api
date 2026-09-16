"""A bad config file must not take down an endpoint.

The config tree is operational data: files get hand-edited, half-written and
occasionally deleted while the service runs. Before this, one malformed file
in ``plots/`` 500'd ``/search`` and
``/visualizations/byInstrument/*`` for every input, and a date with no image on
disk 500'd rather than 404'd -- on the normal path.

These tests use the ``config_root`` fixture, which repoints the app at a
throwaway tree, so they are independent of ``tests/fixtures/config``.
"""

import pytest
from conftest import GOOD_INSTRUMENT, write

# --- one bad file must not hide the good ones -------------------------------

#: YAML accepts much more than JSON did: only the first two of these are parse
#: errors, and the rest are perfectly valid documents that simply are not
#: mappings. Both routes to "unusable" have to be survivable.
BAD_FILES = [
    ("truncated.yaml", "{"),
    ("badindent.yaml", "a: b\n  c: d\n"),
    ("empty.yaml", ""),
    ("notmapping.yaml", "[1, 2, 3]"),
    ("null.yaml", "null"),
    ("text.yaml", "this is just a string\n"),
]


@pytest.mark.parametrize("name,content", BAD_FILES)
def test_bad_site_file_is_skipped(client, populated, name, content):
    write(populated / "sites", name, content)
    r = client.get("/sites")
    assert r.status_code == 200
    assert r.json() == {"good": "Good Site"}


@pytest.mark.parametrize("name,content", BAD_FILES)
def test_bad_instrument_file_is_skipped(client, populated, name, content):
    write(populated / "instruments", name, content)
    assert client.get("/instruments").json() == ["goodinst"]
    r = client.get("/sites/good/instruments")
    assert r.status_code == 200
    assert set(r.json()) == {"goodinst"}


@pytest.mark.parametrize("name,content", BAD_FILES)
def test_bad_plot_file_is_skipped(client, populated, name, content):
    write(populated / "plots", name, content)
    r = client.get("/visualizations/byInstrument/goodinst")
    assert r.status_code == 200
    assert [p["id"] for p in r.json()] == ["goodplot"]


@pytest.mark.parametrize("name,content", BAD_FILES)
def test_search_survives_a_bad_file_in_any_directory(client, populated, name, content):
    for directory in ("sites", "instruments", "plots"):
        write(populated / directory, name, content)
    r = client.get("/search/good")
    assert r.status_code == 200
    assert r.json() == {
        "inst": {"goodinst": "A good instrument"},
        "plots": {"goodplot": "A good plot"},
        "sites": {"good": "Good Site"},
    }


def test_non_yaml_files_are_ignored(client, populated):
    """A stray README used to become a phantom `READ` instrument.

    ``.json`` is listed because the tree used to be JSON: a file left behind by
    the migration must stay inert rather than quietly outvote its replacement.
    """
    write(populated / "instruments", "README.md", "# notes")
    write(populated / "instruments", "goodinst.yaml.bak", GOOD_INSTRUMENT)
    write(populated / "instruments", "goodinst.yml", GOOD_INSTRUMENT)
    write(populated / "instruments", "stale.json", '{"description": "from before"}')
    assert client.get("/instruments").json() == ["goodinst"]


def test_missing_required_keys_are_skipped(client, populated):
    write(populated / "sites", "nameless.yaml", {"lat": 1})
    write(populated / "instruments", "nameless.yaml", {"description": "no name"})
    write(populated / "plots", "plotless.yaml", {"instruments": ["goodinst"]})
    # No `name`, so nothing to label the tile with.
    assert client.get("/sites").json() == {"good": "Good Site"}
    # An instrument's id is its filename, so it is listed even with an empty
    # body; it just has no deployments to show up under a site.
    assert sorted(client.get("/instruments").json()) == ["goodinst", "nameless"]
    assert set(client.get("/sites/good/instruments").json()) == {"goodinst"}
    assert [p["id"] for p in client.get("/visualizations/byInstrument/goodinst").json()] == [
        "goodplot"
    ]


def test_unusable_plot_entries_do_not_take_out_their_neighbours(client, populated):
    """A group file is many plots, so one bad entry must cost only that entry."""
    write(populated / "plots", "mixed.yaml", {
        "instruments": ["goodinst"],
        "plots": {
            "fine": "/nonexistent/%Y%m%d.png",
            "nopath": {"description": "no image path at all"},
            "notamapping": 42,
            "typo": {"dialy": "/nonexistent/%Y%m%d.png"},
        },
    })
    ids = [p["id"] for p in client.get("/visualizations/byInstrument/goodinst").json()]
    assert ids == ["fine", "goodplot"]


def test_a_duplicate_plot_id_does_not_shadow_the_whole_file(client, populated):
    """Ids are unique across the tree, not per file; validate_config.py rejects
    a duplicate, but the running service still has to do something sane."""
    write(populated / "plots", "aaa.yaml", {
        "instruments": ["goodinst"],
        "plots": {"dup": "/first/%Y%m%d.png", "only_in_first": "/x/%Y%m%d.png"},
    })
    write(populated / "plots", "zzz.yaml", {
        "instruments": ["goodinst"],
        "plots": {"dup": "/second/%Y%m%d.png", "only_in_second": "/y/%Y%m%d.png"},
    })
    ids = [p["id"] for p in client.get("/visualizations/byInstrument/goodinst").json()]
    assert ids == ["dup", "goodplot", "only_in_first", "only_in_second"]


def test_malformed_instrument_locations_are_skipped(client, populated):
    write(populated / "instruments", "weird.yaml", {"locations": "nonsense"})
    write(populated / "instruments", "weird2.yaml", {"locations": [None, 3]})
    write(
        populated / "instruments",
        "weird3.yaml",
        {"locations": [{"site": "good", "dates": "nope"}]},
    )
    r = client.get("/sites/good/instruments")
    assert r.status_code == 200
    assert set(r.json()) == {"goodinst"}


# --- a missing directory degrades to empty, not 500 -------------------------


@pytest.mark.parametrize(
    "directory,url,expected",
    [
        ("sites", "/sites", {}),
        ("instruments", "/instruments", []),
        ("instruments", "/sites/good/instruments", {}),
        ("plots", "/visualizations/byInstrument/goodinst", []),
    ],
)
def test_missing_config_directory(client, populated, directory, url, expected):
    for child in (populated / directory).iterdir():
        child.unlink()
    (populated / directory).rmdir()
    r = client.get(url)
    assert r.status_code == 200
    assert r.json() == expected


def test_search_with_no_config_tree_at_all(client, config_root):
    for name in ("plots", "instruments", "sites"):
        (config_root / name).rmdir()
    r = client.get("/search/anything")
    assert r.status_code == 200
    assert r.json() == {"inst": {}, "plots": {}, "sites": {}}


# --- unknown or unusable ids are 404s, not 500s -----------------------------


@pytest.mark.parametrize(
    "url",
    [
        "/sites/nosuchsite",
        "/instruments/nosuchinstrument",
        "/visualizations/byID/nosuchplot/20250101",
        "/visualizations/byID/nosuchplot/daily/20250101",
        "/live/nosuchsite",
    ],
)
def test_unknown_id_is_404(client, populated, url):
    assert client.get(url).status_code == 404


def test_malformed_config_for_a_known_id_is_404_not_500(client, populated):
    write(populated / "plots", "broken.yaml", "{")
    write(populated / "sites", "broken.yaml", "{")
    assert client.get("/visualizations/byID/broken/daily/20250101").status_code == 404
    assert client.get("/live/broken").status_code == 404


def test_plot_without_any_path_is_404(client, populated):
    write(populated / "plots", "pathless.yaml", {"plots": {"pathless": {"description": "x"}}})
    assert client.get("/visualizations/byID/pathless/daily/20250101").status_code == 404


def test_missing_image_file_is_404(client, populated):
    """The normal 'no data for this date' case. It used to be a 500."""
    r = client.get("/visualizations/byID/goodplot/daily/20250101")
    assert r.status_code == 404
    assert "error" in r.json()


# --- identifiers cannot escape the config directory -------------------------


@pytest.mark.parametrize(
    "url",
    [
        "/sites/..%2F..%2Fetc%2Fpasswd",
        "/instruments/..%2F..%2Fetc%2Fpasswd",
        "/visualizations/byID/..%2F..%2Fsecret/daily/20250101",
    ],
)
def test_path_traversal_is_rejected(client, populated, url):
    assert client.get(url).status_code in (400, 404)
