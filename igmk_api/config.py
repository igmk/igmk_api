"""Reading the YAML config tree.

The config tree is operational data, not code: files are hand-edited,
half-written and occasionally deleted while the service is running. So nothing
here raises because of a bad file -- it is logged and skipped, which keeps one
broken group file out of sixty from taking down an endpoint that serves all of
them.

Parsed configs are cached per directory and revalidated against each file's
(mtime, size, inode) on every call, so an edited config is picked up on the next
request without a restart. Each worker holds its own cache; there is nothing to
operate.

This module only parses files. Turning them into the flat records the handlers
want -- expanding plot groups, applying ``base``, mapping file field names onto
wire field names -- is :mod:`igmk_api.index`.
"""

import logging
import os
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

#: File extension of every config file. The stem slice below assumes its length.
SUFFIX = ".yaml"

#: directory -> {filename: (stat_key, parsed config)}. Only successful parses
#: are stored, so a broken file is retried (cheaply) until it is repaired.
_cache: dict[str, dict[str, tuple[tuple[int, int, int], dict]]] = {}


class _ConfigLoader(yaml.SafeLoader):
    """SafeLoader that leaves ISO dates as strings.

    PyYAML resolves an unquoted ``2012-09-12`` to a :class:`datetime.date`,
    which is not JSON-serialisable -- instrument deployment dates are passed
    straight through into the ``timespans`` of ``/sites/{id}/instruments``, so
    the default behaviour turns a perfectly reasonable config file into a 500.
    """


_ConfigLoader.yaml_implicit_resolvers = {
    first: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def clear_cache() -> None:
    """Forget every cached config. Used by tests that swap config trees."""
    _cache.clear()


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
        # S506: _ConfigLoader *is* SafeLoader, minus the timestamp resolver.
        data = yaml.load(raw, Loader=_ConfigLoader)  # noqa: S506
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        log.warning("skipping malformed config %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        log.warning(
            "skipping config %s: expected a YAML mapping, got %s", path, type(data).__name__
        )
        return None
    return data


def _stat_key(st: os.stat_result) -> tuple[int, int, int]:
    # Size and inode join mtime because mtime granularity is filesystem
    # dependent, so a same-tick rewrite could otherwise go unnoticed.
    return (st.st_mtime_ns, st.st_size, st.st_ino)


def load_configs(directory: Path) -> list[tuple[str, dict]]:
    """Return ``(stem, config)`` for every usable ``*.yaml`` in *directory*.

    A missing directory returns nothing, so a partially mounted config tree
    degrades to empty results instead of a 500.
    """
    try:
        entries = [e for e in os.scandir(directory) if e.name.endswith(SUFFIX) and e.is_file()]
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
        configs.append((entry.name[: -len(SUFFIX)], hit[1]))
    # Replacing the dict drops files that have since been deleted.
    _cache[str(directory)] = fresh
    return configs
