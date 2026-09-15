"""Reading the JSON config tree.

Every handler reads its data from ``settings.config_root`` at request time. That
tree is *operational data*, not code: files are hand-edited, half-written, and
occasionally deleted while the service is running. So nothing in this module
raises because of a bad file -- an unreadable, malformed or non-object config is
logged and skipped, which is what keeps one broken plot out of the 445 from
taking down an endpoint that serves all of them.

The rule for handlers: use :func:`iter_configs` when scanning a directory (bad
files vanish from the listing) and :func:`read_config` / :func:`config_path`
when addressing one by id (``None`` means "respond 404").
"""

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def is_safe_stem(stem: str) -> bool:
    """True if *stem* names a file directly inside a config directory.

    Identifiers arrive from URL path segments and are interpolated into
    filesystem paths, so anything that could climb out of the directory
    (``..``, a separator, an absolute path) is rejected rather than sanitised.
    Backslash is rejected too: harmless on POSIX, a separator elsewhere.
    """
    if not stem or stem in {".", ".."} or "\\" in stem:
        return False
    return Path(stem).name == stem


def load_json(path: Path) -> dict | None:
    """Return the JSON object at *path*, or ``None`` if it cannot be used.

    A missing file is silent -- that is an ordinary "unknown id" lookup. Every
    other failure is a broken config and gets logged.
    """
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        log.warning("skipping unreadable config %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        log.warning(
            "skipping config %s: expected a JSON object, got %s", path, type(data).__name__
        )
        return None
    return data


def iter_configs(directory: Path):
    """Yield ``(stem, config)`` for every usable ``*.json`` in *directory*.

    A missing directory yields nothing, so a partially mounted config tree
    degrades to empty results instead of a 500.
    """
    try:
        paths = sorted(directory.glob("*.json"))
    except OSError as exc:
        log.warning("cannot list config directory %s: %s", directory, exc)
        return
    for path in paths:
        config = load_json(path)
        if config is not None:
            yield path.stem, config


def config_path(directory: Path, stem: str) -> Path | None:
    """Return the path of config *stem*, or ``None`` if it is absent or unsafe."""
    if not is_safe_stem(stem):
        return None
    path = directory / f"{stem}.json"
    return path if path.is_file() else None


def read_config(directory: Path, stem: str) -> dict | None:
    """Return config *stem* from *directory*, or ``None`` if unusable."""
    if not is_safe_stem(stem):
        return None
    return load_json(directory / f"{stem}.json")
