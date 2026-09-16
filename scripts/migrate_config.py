#!/usr/bin/env python3
"""One-shot conversion of the old JSON config tree into grouped YAML.

Kept in the repo after the migration because the production tree lives on a
bind mount (``/data/obs/api_config``) and has to be converted separately from
the image -- and because it is the record of how the id spaces were collapsed.

    python3 scripts/migrate_config.py config/ config_new/
"""

import collections
import json
import shutil
import sys
from pathlib import Path

import yaml

GRANULARITIES = ("daily", "monthly", "seasonal", "yearly")

#: Old plot-side instrument reference -> canonical instrument id(s).
#:
#: The canonical id is the old ``name`` field, because that is the space
#: ``/sites/{id}/instruments`` keys by, and therefore the space the frontend's
#: bookmarkable ``pN=site,instrument,plot`` URLs already contain.
INSTRUMENT_ALIASES = {
    "joyrad35": ["joyrad_35"],
    "joyrad94": ["joyrad_94"],
    # Only Doppler wind lidar deployed at jue; all 24 plots sit under
    # .../site/jue/wind_lidar/.
    "windlidar": ["halo"],
    # Combined radar+lidar wind profiles. joyrad35_wind_ppi shares the
    # VAPs/mira_ppi prefix with these, which is what identifies the radar.
    "wind": ["joyrad_35", "halo"],
}

#: Plots where the generic alias above is too coarse.
PLOT_INSTRUMENT_OVERRIDES = {
    # "..._windprofile_lidar.png" -- lidar only, no radar.
    "wind_ppi_dl_only": ["halo"],
}


def q(value) -> str:
    """Render one scalar as YAML, quoting only when YAML requires it."""
    dumped = yaml.safe_dump(value, default_flow_style=True, width=10**9, allow_unicode=True)
    return dumped.rstrip().removesuffix("...").rstrip()


def as_list(value) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    return [v for v in (value or []) if isinstance(v, str) and v]


def render_seq(values: list[str]) -> str:
    return "[" + ", ".join(q(v) for v in values) + "]"


def old_paths(config: dict) -> dict[str, str]:
    """Granularity -> template, normalising the legacy single-``path`` form."""
    paths = config.get("paths")
    if not isinstance(paths, dict):
        path = config.get("path")
        paths = {"daily": path} if isinstance(path, str) else {}
    return {g: p for g in GRANULARITIES if isinstance(p := paths.get(g), str)}


def prefix_of(path: str) -> str:
    """The directory part of *path*, with its trailing slash."""
    return path.rsplit("/", 1)[0] + "/" if "/" in path else ""


def load_plots(src: Path) -> list[dict]:
    """Old plot configs as normalised records, with instrument ids remapped."""
    records = []
    for file in sorted((src / "plots").glob("*.json")):
        config = json.loads(file.read_text())
        # Two files disagree with their own `id`; the field wins, because that
        # is the identifier the live API serves.
        plot_id = config.get("id") or file.stem

        instruments = []
        for ref in as_list(config.get("instruments")):
            for canonical in INSTRUMENT_ALIASES.get(ref, [ref]):
                if canonical not in instruments:
                    instruments.append(canonical)
        instruments = PLOT_INSTRUMENT_OVERRIDES.get(plot_id, instruments)

        records.append({
            "id": plot_id,
            "sites": as_list(config.get("sites")),
            "instruments": instruments,
            "description": config.get("description") or "",
            "multi": bool(config.get("multi")),
            "pattern": config.get("pattern") or None,
            "paths": old_paths(config),
        })
    return records


def group_name(sites: list[str], instruments: list[str]) -> str:
    """A descriptive, non-load-bearing filename for a group."""
    if not sites and not instruments:
        return "unassigned"
    site_part = "_".join(sites) if len(sites) <= 2 else "multisite"
    inst_part = "_".join(instruments) if len(instruments) <= 2 else "multi_instrument"
    name = "-".join(p for p in (site_part, inst_part) if p) or "unassigned"
    return name.replace("/", "_")


def choose_base(group: list[dict]) -> str:
    """The most common directory prefix in the group, or "" if none repeats.

    Only file paths vote: a multi-item plot's path *is* a directory, so
    relativising it would strip the very thing it points at.
    """
    counts = collections.Counter(
        prefix_of(p) for rec in group for p in rec["paths"].values() if not p.endswith("/")
    )
    if not counts:
        return ""
    base, n = counts.most_common(1)[0]
    return base if n > 1 else ""


def render_group(sites: list[str], instruments: list[str], group: list[dict]) -> str:
    base = choose_base(group)
    lines = []
    if sites:
        lines.append(f"sites: {q(sites[0]) if len(sites) == 1 else render_seq(sites)}")
    else:
        lines.append("sites: []")
    if instruments:
        lines.append(
            f"instruments: "
            f"{q(instruments[0]) if len(instruments) == 1 else render_seq(instruments)}"
        )
    else:
        lines.append("instruments: []")
    if base:
        lines.append(f"base: {q(base)}")
    lines.append("")
    lines.append("plots:")

    for rec in sorted(group, key=lambda r: r["id"]):
        paths = {
            g: (p[len(base):] if base and not p.endswith("/") and p.startswith(base) else p)
            for g, p in rec["paths"].items()
        }
        simple = (
            not rec["description"]
            and not rec["multi"]
            and not rec["pattern"]
            and list(paths) == ["daily"]
        )
        if simple:
            lines.append(f"  {q(rec['id'])}: {q(paths['daily'])}")
            continue
        lines.append(f"  {q(rec['id'])}:")
        if rec["description"]:
            lines.append(f"    description: {q(rec['description'])}")
        if rec["multi"]:
            lines.append("    multi: true")
        if rec["pattern"]:
            lines.append(f"    pattern: {q(rec['pattern'])}")
        for gran in GRANULARITIES:
            if gran in paths:
                lines.append(f"    {gran}: {q(paths[gran])}")
    return "\n".join(lines) + "\n"


def migrate_plots(src: Path, dst: Path) -> int:
    records = load_plots(src)
    groups: dict[tuple, list[dict]] = collections.defaultdict(list)
    for rec in records:
        groups[(tuple(rec["sites"]), tuple(rec["instruments"]))].append(rec)

    (dst / "plots").mkdir(parents=True, exist_ok=True)
    used: set[str] = set()
    for (sites, instruments), group in sorted(groups.items(), key=lambda kv: str(kv[0])):
        name = group_name(list(sites), list(instruments))
        candidate, n = name, 2
        while candidate in used:
            candidate, n = f"{name}_{n}", n + 1
        used.add(candidate)
        (dst / "plots" / f"{candidate}.yaml").write_text(
            render_group(list(sites), list(instruments), group)
        )
    return len(groups)


def migrate_instruments(src: Path, dst: Path) -> int:
    """One file per instrument, named by its canonical id (the old ``name``)."""
    (dst / "instruments").mkdir(parents=True, exist_ok=True)
    count = 0
    for file in sorted((src / "instruments").glob("*.json")):
        config = json.loads(file.read_text())
        ident = config.get("name") or file.stem

        lines = [f"description: {q(config.get('description') or '')}"]
        if config.get("wiki"):
            lines.append(f"wiki: {q(config['wiki'])}")
        locations = [loc for loc in (config.get("locations") or []) if isinstance(loc, dict)]
        if locations:
            lines.append("locations:")
            for loc in locations:
                lines.append(f"  - site: {q(loc.get('site') or '')}")
                dates = [d for d in (loc.get("dates") or []) if isinstance(d, list) and d]
                if dates:
                    lines.append("    dates:")
                    # Sorted so the open-ended "still deployed" entry, which is
                    # what _currently_on_site keys on, reliably lands last.
                    for span in sorted(dates, key=lambda d: str(d[0])):
                        lines.append("      - " + render_seq([str(x) for x in span]))
                else:
                    lines.append("    dates: []")
        else:
            lines.append("locations: []")
        (dst / "instruments" / f"{ident}.yaml").write_text("\n".join(lines) + "\n")
        count += 1
    return count


def migrate_sites(src: Path, dst: Path) -> int:
    (dst / "sites").mkdir(parents=True, exist_ok=True)
    count = 0
    for file in sorted((src / "sites").glob("*.json")):
        config = json.loads(file.read_text())
        ident = config.get("siteID") or file.stem
        lines = [
            f"name: {q(config.get('siteHumanReadable') or '')}",
            f"description: {q(config.get('description') or '')}",
        ]
        if config.get("liveDataPath"):
            lines.append(f"live_data: {q(config['liveDataPath'])}")
        for key in ("lat", "lon", "altitude"):
            if config.get(key) is not None:
                lines.append(f"{key}: {q(config[key])}")
        # cgn_bio carries an `instruments` block that no handler has ever read
        # and no schema declares. Preserve it rather than lose it in the
        # conversion; validate_config.py reports it for a human to deal with.
        extra = set(config) - {
            "siteID", "siteHumanReadable", "description", "liveDataPath",
            "lat", "lon", "altitude",
        }
        for key in sorted(extra):
            lines.append(yaml.safe_dump({key: config[key]}, allow_unicode=True,
                                        sort_keys=True, width=10**9).rstrip())
        (dst / "sites" / f"{ident}.yaml").write_text("\n".join(lines) + "\n")
        count += 1
    return count


def main() -> int:
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "config")
    dst = Path(sys.argv[2] if len(sys.argv) > 2 else "config_new")
    if dst.exists():
        shutil.rmtree(dst)
    n_plots = migrate_plots(src, dst)
    n_inst = migrate_instruments(src, dst)
    n_sites = migrate_sites(src, dst)
    old = sum(f.stat().st_size for f in src.rglob("*.json"))
    new = sum(f.stat().st_size for f in dst.rglob("*.yaml"))
    print(f"plots        {len(list((src / 'plots').glob('*.json')))} files -> {n_plots} groups")
    print(f"instruments  {n_inst} files")
    print(f"sites        {n_sites} files")
    print(f"bytes        {old} -> {new}  ({100 * new // old}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
