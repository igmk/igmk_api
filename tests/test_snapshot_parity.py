"""The JSON -> YAML config migration must not have changed the API.

``tests/fixtures/api_snapshot.json`` was captured by ``scripts/snapshot_api.py``
against the *old* JSON tree running the *old* code, and committed before any of
this was touched. This file replays it against the real ``config/`` tree.

The cut-over was clean -- there is no dual-format loader to fall back on -- so
this is the evidence that the conversion was faithful. Every difference has to
be named here with a reason; anything else is a bug.
"""

import json
import sys
from pathlib import Path

import pytest

from igmk_api.config import clear_cache
from igmk_api.settings import settings

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from snapshot_api import collect_plots, resolve  # noqa: E402

SNAPSHOT = json.loads((REPO / "tests" / "fixtures" / "api_snapshot.json").read_text())

#: Endpoints whose response is *supposed* to differ, and why. Collapsing the two
#: instrument id spaces was the point of the exercise; the rest is fallout from
#: it, plus two data fixes.
ALLOWED_CHANGES = {
    # -- one id space: an instrument's id is now its filename, and the filename
    #    is the old `name` field, which is what /sites/{id}/instruments always
    #    keyed by (and so what the frontend's bookmarkable URLs contain).
    "/instruments": "_halo_rpg/joyrad_10/raman_lidar renamed to halo_rpg/joyrad/raman",
    "/instruments/halo_rpg": "was 404; the file was named _halo_rpg",
    "/instruments/joyrad": "was 404; the file was named joyrad_10",
    "/instruments/raman": "was 404; the file was named raman_lidar",
    # -- plots that pointed at instrument ids with no instrument file. These
    #    were unreachable by navigation: the frontend only ever offers ids that
    #    /sites/{id}/instruments lists.
    "/visualizations/byInstrument/halo": "gains windlidar's 24 and wind's 9 plots",
    "/visualizations/byInstrument/joyrad_35": "gains joyrad35's 16 and wind's 8 plots",
    "/visualizations/byInstrument/joyrad_94": "gains joyrad94's 4 plots",
    # -- deployment spans are now emitted oldest-first, so the "still deployed"
    #    entry that _currently_on_site() reads is genuinely last. Membership is
    #    asserted unchanged below; only the order of `timespans` moved.
    "/instruments/halo": "deployment spans sorted",
    "/sites/jue/instruments": "halo's timespans sorted",
    "/sites/jue/instruments/history": "halo's timespans sorted",
    # -- data fixes surfaced by scripts/validate_config.py.
    "/instruments/foghat": "2024-06-31 is not a date; corrected to 2024-06-30",
    "/sites/cgn_bio/instruments": "foghat's corrected end date",
    "/sites/cgn_bio/instruments/history": "foghat's corrected end date",
    # -- /sites/{id} used to send_file the raw config, so undeclared keys leaked
    #    out. It now serves exactly what openapi.yaml declares. The dropped data
    #    is preserved in config/sites/cgn_bio.yaml.
    "/sites/cgn_bio": "stops serving an undeclared `instruments` block",
    # -- plots are ordered by id rather than by config filename, which differed
    #    only where a '-' sorted against the old '.json' suffix.
    "/visualizations/byInstrument/wls_aac": "'chart' now sorts before 'chart-dw'",
}

#: Ids that existed only because the two id spaces disagreed. Nothing could
#: navigate to them, so retiring them breaks no link a user could hold.
RETIRED_IDS = [
    "_halo_rpg", "joyrad_10", "raman_lidar",  # renamed to their `name`
    "joyrad35", "joyrad94",                   # typo'd references, no such file
    "wind", "windlidar",                      # aliases of joyrad_35 / halo
]


@pytest.fixture
def real_config():
    """Point the app at the repo's actual config tree, not the fixture tree."""
    original = settings.config_root
    settings.config_root = REPO / "config"
    clear_cache()
    yield
    settings.config_root = original
    clear_cache()


def test_no_plot_image_url_changed(real_config):
    """The load-bearing assertion: every plot still resolves to the same bytes.

    445 plots x every granularity they declare -- if grouping, `base` joining or
    the shorthand form got any of this wrong, an image 404s for a scientist and
    nothing else would notice.
    """
    assert resolve(collect_plots()) == SNAPSHOT["resolved"]


def test_the_same_plots_exist(real_config):
    assert sorted(collect_plots()) == sorted(SNAPSHOT["plots"])


def test_plot_multi_and_pattern_are_unchanged(real_config):
    """`multi`/`pattern` drive the item-listing routes, which the browser uses."""
    plots = collect_plots()
    for plot_id, old in SNAPSHOT["plots"].items():
        for field in ("multi", "pattern", "description"):
            assert plots[plot_id][field] == old[field], f"{plot_id}.{field}"


def test_only_the_intended_endpoints_changed(client, real_config):
    differing = {}
    for url, old in SNAPSHOT["endpoints"].items():
        if any(url.endswith(f"/{retired}") for retired in RETIRED_IDS):
            continue
        r = client.get(url)
        try:
            body = r.json()
        except ValueError:
            body = r.text
        if {"status": r.status_code, "body": body} != old:
            differing[url] = body
    assert set(differing) == set(ALLOWED_CHANGES), (
        f"unexpected: {sorted(set(differing) - set(ALLOWED_CHANGES))}, "
        f"no longer differing: {sorted(set(ALLOWED_CHANGES) - set(differing))}"
    )


def test_site_instrument_membership_is_unchanged(client, real_config):
    """The timespan *order* moved; which instruments a site lists must not."""
    for url, old in SNAPSHOT["endpoints"].items():
        if "/instruments" in url and url.startswith("/sites/"):
            assert set(client.get(url).json()) == set(old["body"]), url


def test_retired_instrument_ids_are_gone(client, real_config):
    for retired in RETIRED_IDS:
        assert client.get(f"/instruments/{retired}").status_code == 404, retired
        assert client.get(f"/visualizations/byInstrument/{retired}").json() == [], retired


def test_every_plot_is_reachable_from_an_instrument(client, real_config):
    """What the id collapse was for: an id from /instruments now answers on
    byInstrument, and every plot bar the three unassigned ones is reachable."""
    reachable = set()
    for instrument_id in client.get("/instruments").json():
        body = client.get(f"/visualizations/byInstrument/{instrument_id}").json()
        reachable.update(p["id"] for p in body)
    unreachable = set(collect_plots()) - reachable
    assert unreachable == {"data_space", "data_obs_space", "data_space_multi"}
