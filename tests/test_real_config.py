"""The config tree that actually ships must be valid.

Nothing used to parse ``config/``: the suite points at ``tests/fixtures/config``
instead, so a change that broke all 445 production plot configs would have gone
out with a green build. The loader's "log it and skip it" policy is right for a
running service but means a typo costs a silently missing plot, not an error --
so the tree gets checked here instead.
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from validate_config import (  # noqa: E402
    Report,
    check_instruments,
    check_plots,
    check_sites,
    check_stray_files,
)

CONFIG = REPO / "config"

#: Warnings the tree is knowingly shipping. Pinned rather than ignored, so a
#: *new* one fails the build -- a mistyped site id would otherwise be just
#: another line in a long list.
KNOWN_WARNINGS = {
    # Deployment history at Arctic sites this API instance does not serve.
    "instrument deployed at a site with no config": 9,
    # Four upstream URLs are still plain http.
    "plain http, not https": 4,
    # Disk-space plots that belong to no instrument, so nothing links to them.
    "no instruments, so nothing links to it": 3,
    # cgn_bio carries an instruments block no handler reads; preserved, not served.
    "unknown keys, ignored by the API": 1,
}


@pytest.fixture(scope="module")
def report() -> Report:
    report = Report()
    check_stray_files(CONFIG, report)
    site_ids = check_sites(CONFIG, report)
    instrument_ids = check_instruments(CONFIG, site_ids, report)
    check_plots(CONFIG, site_ids, instrument_ids, report)
    return report


def test_config_tree_has_no_errors(report):
    assert report.errors == []


def test_config_tree_warnings_are_the_known_ones(report):
    counts = {key: 0 for key in KNOWN_WARNINGS}
    unrecognised = []
    for line in report.warnings:
        for key in KNOWN_WARNINGS:
            if key in line or (key.startswith("instrument deployed") and "has no config" in line):
                counts[key] += 1
                break
        else:
            unrecognised.append(line)
    assert unrecognised == [], "new warning in config/; fix it or pin it here"
    assert counts == KNOWN_WARNINGS


def test_every_plot_id_is_unique_across_the_tree(report):
    """Ids are global, not per file -- the group filename means nothing."""
    assert not [line for line in report.errors if "already defined" in line]
