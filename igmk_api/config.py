"""Reading the JSON config tree.

The config tree is operational data, not code: files are hand-edited,
half-written and occasionally deleted while the service is running. So nothing
here raises because of a bad file -- it is logged and skipped, which keeps one
broken plot out of 445 from taking down an endpoint that serves all of them.

Parsed configs are cached per directory and revalidated against each file's
(mtime, size, inode) on every call, so an edited config is picked up on the next
request without a restart. Each worker holds its own cache; there is nothing to
operate.

Handlers use :func:`load_configs` to scan a directory and :func:`read_config` /
:func:`config_path` to address one file by id, where ``None`` means "respond
404".
"""

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

#: directory -> {filename: (stat_key, parsed config)}. Only successful parses
#: are stored, so a broken file is retried (cheaply) until it is repaired.
_cache: dict[str, dict[str, tuple[tuple[int, int, int], dict]]] = {}


def clear_cache() -> None:
    """Forget every cached config. Used by tests that swap config trees."""
    _cache.clear()


def is_safe_stem(stem: str) -> bool:
    """True if *stem* names a file directly inside a config directory.

    Identifiers arrive from URL path segments and are interpolated into
    filesystem paths, so anything that could climb out of the directory is
    rejected rather than sanitised. Backslash is rejected too: harmless on
    POSIX, a separator elsewhere.
    """
    if not stem or stem in {".", ".."} or "\\" in stem:
        return False
    return Path(stem).name == stem


def _load(path: str) -> dict | None:
    """Read and parse one config file; ``None`` if it cannot be used."""
    try:
        raw = Path(path).read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        log.warning("skipping unreadable config %s: %s", path, exc)
        return None
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        log.warning("skipping malformed config %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        log.warning(
            "skipping config %s: expected a JSON object, got %s", path, type(data).__name__
        )
        return None
    return data


def _stat_key(st: os.stat_result) -> tuple[int, int, int]:
    # Size and inode join mtime because mtime granularity is filesystem
    # dependent, so a same-tick rewrite could otherwise go unnoticed.
    return (st.st_mtime_ns, st.st_size, st.st_ino)


def load_configs(directory: Path) -> list[tuple[str, dict]]:
    """Return ``(stem, config)`` for every usable ``*.json`` in *directory*.

    A missing directory returns nothing, so a partially mounted config tree
    degrades to empty results instead of a 500.
    """
    try:
        entries = [e for e in os.scandir(directory) if e.name.endswith(".json") and e.is_file()]
    except FileNotFoundError:
        return []
    except OSError as exc:
        log.warning("cannot list config directory %s: %s", directory, exc)
        return []

    cached = _cache.get(str(directory), {})
    fresh: dict[str, tuple[tuple[int, int, int], dict]] = {}
    configs = []
    for entry in sorted(entries, key=lambda e: e.name):
        key = _stat_key(entry.stat())
        hit = cached.get(entry.name)
        if hit is None or hit[0] != key:
            config = _load(entry.path)
            if config is None:
                continue
            hit = (key, config)
        fresh[entry.name] = hit
        configs.append((entry.name[:-5], hit[1]))
    # Replacing the dict drops files that have since been deleted.
    _cache[str(directory)] = fresh
    return configs


def config_path(directory: Path, stem: str) -> Path | None:
    """Return the path of config *stem*, or ``None`` if absent or unsafe."""
    if not is_safe_stem(stem):
        return None
    path = directory / f"{stem}.json"
    return path if path.is_file() else None


def read_config(directory: Path, stem: str) -> dict | None:
    """Return config *stem* from *directory*, or ``None`` if unusable."""
    if not is_safe_stem(stem):
        return None
    name = f"{stem}.json"
    path = directory / name
    try:
        key = _stat_key(path.stat())
    except OSError:
        return None
    cached = _cache.setdefault(str(directory), {})
    hit = cached.get(name)
    if hit is None or hit[0] != key:
        config = _load(str(path))
        if config is None:
            cached.pop(name, None)
            return None
        hit = (key, config)
        cached[name] = hit
    return hit[1]
