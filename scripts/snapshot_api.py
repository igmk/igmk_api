#!/usr/bin/env python3
"""Capture the API's observable behaviour as a JSON snapshot.

This is the regression oracle for the config format migration. It is run once
against the old JSON tree to record what the API did, committed, and then
asserted against by ``tests/test_snapshot_parity.py`` for the new YAML tree.

Deliberately implementation-agnostic: it talks HTTP for everything it can, and
for plot templates -- which can only be observed by fetching an image -- it asks
whichever plot index the package currently exposes. So the same script produces
comparable output before and after the migration.

    IGMK_CONFIG_ROOT=./config python3 scripts/snapshot_api.py tests/fixtures/api_snapshot.json
"""

import datetime
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

os.environ.setdefault("IGMK_CONFIG_ROOT", str(REPO / "config"))

#: Dates used to resolve every strftime template. Fixed, so the snapshot is
#: reproducible; chosen so %d/%m/%Y are all distinguishable in the output.
SAMPLE_DATES = {
    "daily": datetime.datetime(2026, 6, 15),
    "monthly": datetime.datetime(2026, 6, 1),
    "seasonal": datetime.datetime(2026, 6, 1),
    "yearly": datetime.datetime(2026, 1, 1),
}

SEARCH_QUERIES = ["tke", "wind", "jue", "radar", "temp", "skew", "halo", "hatpro", "zzznomatch"]


def collect_plots() -> dict[str, dict]:
    """plot id -> {sites, instruments, description, multi, pattern, paths}.

    Uses the new normalisation layer when it exists, else the old loader.
    """
    try:
        from igmk_api.index import plot_index
    except ImportError:
        pass
    else:
        out = {}
        for plot_id, rec in plot_index().items():
            out[plot_id] = {
                "sites": sorted(rec.get("sites") or []),
                "instruments": sorted(rec.get("instruments") or []),
                "description": rec.get("description") or "",
                "multi": bool(rec.get("multi")),
                "pattern": rec.get("pattern") or None,
                "paths": dict(rec.get("paths") or {}),
            }
        return out

    from igmk_api.api.plots import _plot_paths
    from igmk_api.config import load_configs
    from igmk_api.settings import settings

    out = {}
    for _stem, config in load_configs(settings.plots_dir):
        plot_id = config.get("id")
        if not plot_id:
            continue
        out[plot_id] = {
            "sites": sorted(config.get("sites") or []),
            "instruments": sorted(config.get("instruments") or []),
            "description": config.get("description") or "",
            "multi": bool(config.get("multi")),
            "pattern": config.get("pattern") or None,
            "paths": _plot_paths(config),
        }
    return out


def resolve(plots: dict[str, dict]) -> dict[str, dict[str, str]]:
    """plot id -> granularity -> the fully resolved path or URL."""
    return {
        plot_id: {
            gran: SAMPLE_DATES[gran].strftime(template)
            for gran, template in sorted(rec["paths"].items())
        }
        for plot_id, rec in plots.items()
    }


def get(client, url):
    """Fetch *url*, recording status and body (JSON when possible)."""
    r = client.get(url)
    try:
        body = r.json()
    except ValueError:
        body = r.text
    return {"status": r.status_code, "body": body}


def main() -> int:
    out_path = Path(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/api_snapshot.json")

    from starlette.testclient import TestClient

    from igmk_api.app import app
    from igmk_api.config import load_configs
    from igmk_api.settings import settings

    plots = collect_plots()

    # Every identifier that anything might address an instrument by: filename
    # stems, `name` fields, and whatever the plots reference. The union is the
    # point -- it is exactly where the two id spaces drift apart.
    instrument_ids = set()
    for stem, config in load_configs(settings.instruments_dir):
        instrument_ids.add(stem)
        if isinstance(config.get("name"), str):
            instrument_ids.add(config["name"])
    try:
        from igmk_api.index import instrument_index

        instrument_ids.update(instrument_index())
    except ImportError:
        pass
    for rec in plots.values():
        instrument_ids.update(rec["instruments"])
    instrument_ids.discard("")

    site_ids = set()
    for stem, config in load_configs(settings.sites_dir):
        site_ids.add(stem)
        if isinstance(config.get("siteID"), str):
            site_ids.add(config["siteID"])
    try:
        from igmk_api.index import site_index

        site_ids.update(site_index())
    except ImportError:
        pass

    with TestClient(app) as client:
        snapshot = {
            "plots": plots,
            "resolved": resolve(plots),
            "endpoints": {},
        }
        eps = snapshot["endpoints"]
        eps["/sites"] = get(client, "/sites")
        eps["/instruments"] = get(client, "/instruments")
        for sid in sorted(site_ids):
            eps[f"/sites/{sid}"] = get(client, f"/sites/{sid}")
            eps[f"/sites/{sid}/instruments"] = get(client, f"/sites/{sid}/instruments")
            eps[f"/sites/{sid}/instruments/history"] = get(
                client, f"/sites/{sid}/instruments/history"
            )
        for iid in sorted(instrument_ids):
            eps[f"/instruments/{iid}"] = get(client, f"/instruments/{iid}")
            eps[f"/visualizations/byInstrument/{iid}"] = get(
                client, f"/visualizations/byInstrument/{iid}"
            )
        for q in SEARCH_QUERIES:
            eps[f"/search/{q}"] = get(client, f"/search/{q}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, indent=1, sort_keys=True, ensure_ascii=False) + "\n")

    n_res = sum(len(v) for v in snapshot["resolved"].values())
    print(f"plots           {len(plots)}")
    print(f"resolved paths  {n_res}")
    print(f"endpoints       {len(eps)}")
    print(f"wrote           {out_path} ({out_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
