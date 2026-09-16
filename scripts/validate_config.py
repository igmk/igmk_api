#!/usr/bin/env python3
"""Check a config tree before it reaches the service.

The API deliberately never fails on a bad config -- it logs the file and skips
it -- which is right for a service whose config is hand-edited while it runs,
but it means a typo shows up as a quietly missing plot rather than an error.
This is the other half of that bargain: run it after editing and it tells you.

    python3 scripts/validate_config.py config/

Exit status is 0 when there are no errors. Warnings never fail the run on their
own; pass --strict to treat them as errors too.
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml

from igmk_api.config import SUFFIX, _ConfigLoader
from igmk_api.index import (
    GRANULARITY_FORMATS,
    GROUP_KEYS,
    PLOT_KEYS,
    as_list,
    join_base,
)

#: Same pattern openapi.yaml enforces on visID/siteID/instrumentID, so an id
#: that fails here would 400 before ever reaching a handler.
ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")

SITE_KEYS = {"name", "description", "live_data", "lat", "lon", "altitude"}
INSTRUMENT_KEYS = {"description", "wiki", "locations"}
LOCATION_KEYS = {"site", "dates"}

DIRECTORIES = ("plots", "instruments", "sites")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: Path | str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def warn(self, where: Path | str, message: str) -> None:
        self.warnings.append(f"{where}: {message}")


def load(path: Path, report: Report) -> dict | None:
    try:
        # S506: _ConfigLoader is SafeLoader without the timestamp resolver.
        data = yaml.load(path.read_bytes(), Loader=_ConfigLoader)  # noqa: S506
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        report.error(path, f"will not parse -- {str(exc).splitlines()[0]}")
        return None
    if not isinstance(data, dict):
        report.error(path, f"must be a mapping, got {type(data).__name__}")
        return None
    return data


def check_stray_files(root: Path, report: Report) -> None:
    for directory in DIRECTORIES:
        d = root / directory
        if not d.is_dir():
            report.error(root, f"missing directory {directory}/")
            continue
        for path in sorted(d.iterdir()):
            if path.is_dir():
                report.error(path, "subdirectories are not scanned")
            elif path.suffix == ".json":
                report.error(path, "left over from the JSON config; delete it")
            elif path.suffix == ".yml":
                report.error(path, f"the loader only reads {SUFFIX}; rename it")
            elif path.suffix != SUFFIX:
                report.warn(path, f"not a {SUFFIX} file, so it is ignored")


def check_dates(where: Path, label: str, dates, report: Report) -> None:
    if not isinstance(dates, list):
        report.error(where, f"{label}: `dates` must be a list of spans")
        return
    open_ended_at = None
    for i, span in enumerate(dates):
        if not isinstance(span, list) or not 1 <= len(span) <= 2:
            report.error(where, f"{label}: each span needs 1 or 2 dates, got {span!r}")
            continue
        for value in span:
            if not isinstance(value, str):
                report.error(where, f"{label}: {value!r} must be quoted as a string")
                continue
            try:
                datetime.date.fromisoformat(value)
            except ValueError:
                report.error(where, f"{label}: {value!r} is not a YYYY-MM-DD date")
        if len(span) == 2 and all(isinstance(v, str) for v in span) and span[0] > span[1]:
            report.error(where, f"{label}: span {span!r} ends before it starts")
        if len(span) == 1:
            open_ended_at = i
    if open_ended_at is not None and open_ended_at != len(dates) - 1:
        # _currently_on_site() reads dates[-1], so an open-ended span anywhere
        # else means the instrument silently drops off its site listing.
        report.error(
            where,
            f"{label}: the open-ended span must be last, or the instrument will "
            f"not count as currently on site",
        )


def check_instruments(root: Path, site_ids: set[str], report: Report) -> set[str]:
    ids = set()
    for path in sorted((root / "instruments").glob(f"*{SUFFIX}")):
        ids.add(path.stem)
        config = load(path, report)
        if config is None:
            continue
        if not ID_PATTERN.match(path.stem):
            report.error(path, f"id {path.stem!r} must match {ID_PATTERN.pattern}")
        if unknown := set(config) - INSTRUMENT_KEYS:
            report.warn(path, f"unknown keys, ignored by the API: {sorted(unknown)}")
        if not config.get("description"):
            report.warn(path, "no description, so its tile shows a bare id")
        locations = config.get("locations")
        if locations is None:
            report.warn(path, "no locations, so it appears under no site")
            continue
        if not isinstance(locations, list):
            report.error(path, "`locations` must be a list")
            continue
        for i, location in enumerate(locations):
            label = f"locations[{i}]"
            if not isinstance(location, dict):
                report.error(path, f"{label}: must be a mapping")
                continue
            if unknown := set(location) - LOCATION_KEYS:
                report.warn(path, f"{label}: unknown keys {sorted(unknown)}")
            site = location.get("site")
            if not site:
                report.error(path, f"{label}: no `site`")
            elif site not in site_ids:
                # A warning, not an error: several instruments carry real
                # deployment history from sites this API does not serve (`nya`,
                # `iqu`). The record is worth keeping; it simply matches no
                # /sites/{id}/instruments query.
                report.warn(path, f"site {site!r} has no config, so this deployment is invisible")
            check_dates(path, label, location.get("dates", []), report)
    return ids


def check_sites(root: Path, report: Report) -> set[str]:
    ids = set()
    for path in sorted((root / "sites").glob(f"*{SUFFIX}")):
        ids.add(path.stem)
        config = load(path, report)
        if config is None:
            continue
        if not ID_PATTERN.match(path.stem):
            report.error(path, f"id {path.stem!r} must match {ID_PATTERN.pattern}")
        if unknown := set(config) - SITE_KEYS:
            report.warn(path, f"unknown keys, ignored by the API: {sorted(unknown)}")
        if not config.get("name"):
            report.error(path, "no `name`, so the site is left out of /sites entirely")
        for key in ("lat", "lon"):
            if not isinstance(config.get(key), (int, float)):
                report.warn(path, f"`{key}` is missing or not a number")
    return ids


def check_plots(root: Path, site_ids: set[str], instrument_ids: set[str], report: Report) -> int:
    seen: dict[str, Path] = {}
    for path in sorted((root / "plots").glob(f"*{SUFFIX}")):
        config = load(path, report)
        if config is None:
            continue
        if unknown := set(config) - GROUP_KEYS:
            report.error(path, f"unknown top-level keys: {sorted(unknown)}")
        base = config.get("base", "")
        if base and not isinstance(base, str):
            report.error(path, "`base` must be a string")
            base = ""
        if base and not base.endswith("/"):
            report.error(path, f"`base` must end with '/', got {base!r}")
        group_sites = as_list(config.get("sites"))
        group_instruments = as_list(config.get("instruments"))

        plots = config.get("plots")
        if not isinstance(plots, dict):
            report.error(path, "no `plots` mapping, so the whole file is ignored")
            continue

        for plot_id, body in plots.items():
            if not isinstance(plot_id, str) or not ID_PATTERN.match(plot_id):
                report.error(path, f"plot id {plot_id!r} must match {ID_PATTERN.pattern}")
                continue
            if plot_id in seen:
                report.error(path, f"plot id {plot_id!r} is already defined in {seen[plot_id]}")
                continue
            seen[plot_id] = path

            if isinstance(body, str):
                body = {"daily": body}
            if not isinstance(body, dict):
                report.error(path, f"{plot_id}: must be a path string or a mapping")
                continue
            if unknown := set(body) - PLOT_KEYS:
                # `path`/`paths` are the old JSON spelling and by far the most
                # likely mistake, so say where the granularities went.
                stale = unknown & {"path", "paths", "id"}
                hint = " -- granularity keys go inline (daily/monthly/...)" if stale else ""
                report.error(path, f"{plot_id}: unknown keys {sorted(unknown)}{hint}")

            templates = {g: body[g] for g in GRANULARITY_FORMATS if isinstance(body.get(g), str)}
            if not templates:
                report.error(path, f"{plot_id}: declares no image path, so it 404s")
            multi = bool(body.get("multi"))
            for gran, template in templates.items():
                if not base and not (template.startswith("/") or "://" in template):
                    report.error(
                        path, f"{plot_id}.{gran}: relative path {template!r} but no `base`"
                    )
                resolved = join_base(base, template)
                # A multi-item plot resolves to a directory; its date lives in
                # `pattern`, which is checked below.
                if not multi and "%" not in resolved and gran != "seasonal":
                    report.warn(
                        path,
                        f"{plot_id}.{gran}: no strftime directive in {resolved!r}, so "
                        f"every date serves the same image",
                    )
                if resolved.startswith("http://"):
                    report.warn(path, f"{plot_id}.{gran}: plain http, not https")

            pattern = body.get("pattern")
            if multi and isinstance(pattern, str) and "%" not in pattern:
                report.warn(
                    path,
                    f"{plot_id}: `pattern` has no strftime directive, so every date "
                    f"lists the same items",
                )
            if multi != ("pattern" in body):
                report.error(path, f"{plot_id}: `multi` and `pattern` must be used together")
            if multi:
                daily = templates.get("daily", "")
                if daily and not daily.endswith("/"):
                    report.error(
                        path,
                        f"{plot_id}: a multi-item path is a directory and must end with '/'",
                    )

            for site in as_list(body["sites"]) if "sites" in body else group_sites:
                if site not in site_ids:
                    report.error(path, f"{plot_id}: unknown site {site!r}")
            refs = as_list(body["instruments"]) if "instruments" in body else group_instruments
            for instrument in refs:
                if instrument not in instrument_ids:
                    report.error(path, f"{plot_id}: unknown instrument {instrument!r}")
            if not refs:
                report.warn(path, f"{plot_id}: no instruments, so nothing links to it")
    return len(seen)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default="config", type=Path)
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args()

    report = Report()
    check_stray_files(args.root, report)
    site_ids = check_sites(args.root, report)
    instrument_ids = check_instruments(args.root, site_ids, report)
    n_plots = check_plots(args.root, site_ids, instrument_ids, report)

    for line in report.errors:
        print(f"error   {line}")
    for line in report.warnings:
        print(f"warning {line}")
    print(
        f"\n{n_plots} plots, {len(instrument_ids)} instruments, {len(site_ids)} sites"
        f"  --  {len(report.errors)} error(s), {len(report.warnings)} warning(s)"
    )
    return 1 if report.errors or (args.strict and report.warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
