"""Unit tests for the config loader itself.

Endpoint-level degradation is covered by test_resilience.py; this file tests
igmk_api/config.py directly, where a fixture tree would be indirection.
"""

import json

import pytest

from igmk_api.config import config_path, is_safe_stem, load_configs, read_config


@pytest.mark.parametrize(
    "stem", ["..", ".", "", "../etc/passwd", "a/b", "a\\b", "/etc/passwd", "sub/dir"]
)
def test_is_safe_stem_rejects_traversal(stem):
    """`.` and `..` cannot be reached over HTTP -- clients normalise them away --
    so the guard is checked directly."""
    assert not is_safe_stem(stem)


@pytest.mark.parametrize("stem", ["good", "_halo_rpg", "joyrad_10", "uv-index", "aac_RH"])
def test_is_safe_stem_accepts_real_ids(stem):
    assert is_safe_stem(stem)


def test_load_configs_skips_undecodable_bytes(tmp_path, caplog):
    """Not valid UTF-8 -- distinct from malformed JSON."""
    (tmp_path / "bad.json").write_bytes(b'{"name": "\xff\xfe"}')
    (tmp_path / "good.json").write_text(json.dumps({"name": "ok"}))
    assert load_configs(tmp_path) == [("good", {"name": "ok"})]
    assert "bad.json" in caplog.text


def test_load_configs_survives_unreadable_directory(tmp_path, caplog):
    """The `except OSError` branch: a directory that exists but cannot be listed."""
    unreadable = tmp_path / "locked"
    unreadable.mkdir(mode=0o000)
    try:
        assert load_configs(unreadable) == []
    finally:
        unreadable.chmod(0o755)


def test_load_configs_is_sorted_by_stem(tmp_path):
    for name in ("c", "a", "b"):
        (tmp_path / f"{name}.json").write_text("{}")
    assert [stem for stem, _ in load_configs(tmp_path)] == ["a", "b", "c"]


def test_read_config_returns_none_for_missing_and_malformed(tmp_path):
    (tmp_path / "broken.json").write_text("{")
    assert read_config(tmp_path, "absent") is None
    assert read_config(tmp_path, "broken") is None
    assert read_config(tmp_path, "../escape") is None


def test_config_path_only_returns_existing_files(tmp_path):
    (tmp_path / "there.json").write_text("{}")
    assert config_path(tmp_path, "there") == tmp_path / "there.json"
    assert config_path(tmp_path, "absent") is None
    assert config_path(tmp_path, "../escape") is None


# --- the cache must never serve stale content ------------------------------


def test_cache_picks_up_an_edit(tmp_path):
    f = tmp_path / "x.json"
    f.write_text(json.dumps({"v": 1}))
    assert load_configs(tmp_path) == [("x", {"v": 1})]
    f.write_text(json.dumps({"v": 2}))
    assert load_configs(tmp_path) == [("x", {"v": 2})]
    assert read_config(tmp_path, "x") == {"v": 2}


def test_cache_picks_up_add_and_delete(tmp_path):
    (tmp_path / "a.json").write_text("{}")
    assert [s for s, _ in load_configs(tmp_path)] == ["a"]
    (tmp_path / "b.json").write_text("{}")
    assert [s for s, _ in load_configs(tmp_path)] == ["a", "b"]
    (tmp_path / "a.json").unlink()
    assert [s for s, _ in load_configs(tmp_path)] == ["b"]


def test_cache_recovers_when_a_broken_file_is_repaired(tmp_path):
    f = tmp_path / "x.json"
    f.write_text(json.dumps({"v": 1}))
    assert load_configs(tmp_path) == [("x", {"v": 1})]
    f.write_text("{ broken")
    assert load_configs(tmp_path) == []
    assert read_config(tmp_path, "x") is None
    f.write_text(json.dumps({"v": 3}))
    assert load_configs(tmp_path) == [("x", {"v": 3})]


def test_deleting_a_file_does_not_leak_into_a_reused_name(tmp_path):
    """A stale cache entry must not resurrect content under a recreated name."""
    f = tmp_path / "x.json"
    f.write_text(json.dumps({"v": "old"}))
    load_configs(tmp_path)
    f.unlink()
    assert load_configs(tmp_path) == []
    f.write_text(json.dumps({"v": "new"}))
    assert load_configs(tmp_path) == [("x", {"v": "new"})]
