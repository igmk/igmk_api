"""Unit tests for the config loader itself.

Endpoint-level degradation is covered by test_resilience.py; this file tests
igmk_api/config.py directly, where a fixture tree would be indirection.
"""

import pytest
import yaml

from igmk_api.config import load_configs


def test_dates_stay_strings(tmp_path):
    """The single most dangerous thing about YAML here.

    PyYAML resolves an unquoted ``2012-09-12`` to a ``datetime.date``, and
    instrument deployment dates are passed straight through into the
    ``timespans`` of /sites/{id}/instruments -- where Flask has to JSON-encode
    them. Left alone, a scientist writing a perfectly ordinary date turns that
    endpoint into a 500.
    """
    (tmp_path / "x.yaml").write_text("dates:\n  - [2012-09-12, 2025-01-22]\n  - [2026-06-01]\n")
    ((_stem, config),) = load_configs(tmp_path)
    assert config == {"dates": [["2012-09-12", "2025-01-22"], ["2026-06-01"]]}
    assert all(isinstance(d, str) for span in config["dates"] for d in span)


def test_load_configs_skips_undecodable_bytes(tmp_path, caplog):
    """Not valid UTF-8 -- distinct from malformed YAML."""
    (tmp_path / "bad.yaml").write_bytes(b'name: "\xff\xfe"')
    (tmp_path / "good.yaml").write_text("name: ok\n")
    assert load_configs(tmp_path) == [("good", {"name": "ok"})]
    assert "bad.yaml" in caplog.text


@pytest.mark.parametrize(
    "text",
    [
        "{",                      # unterminated flow mapping
        "[unclosed",              # unterminated flow sequence
        "a: b\n  c: d\n",         # bad indentation
        "a: *nosuchanchor\n",     # undefined alias
        "\ta: b\n",               # tab indentation
    ],
)
def test_load_configs_skips_malformed_yaml(tmp_path, caplog, text):
    (tmp_path / "bad.yaml").write_text(text)
    (tmp_path / "good.yaml").write_text("name: ok\n")
    assert load_configs(tmp_path) == [("good", {"name": "ok"})]
    assert "bad.yaml" in caplog.text


@pytest.mark.parametrize("text", ["", "null\n", "- 1\n- 2\n", "just a string\n"])
def test_load_configs_skips_documents_that_are_not_mappings(tmp_path, caplog, text):
    """YAML parses far more than JSON did: an empty file, a bare scalar and a
    bare list are all *valid* documents, so the mapping check is what rejects
    them rather than a parse error."""
    (tmp_path / "bad.yaml").write_text(text)
    (tmp_path / "good.yaml").write_text("name: ok\n")
    assert load_configs(tmp_path) == [("good", {"name": "ok"})]
    assert "bad.yaml" in caplog.text


def test_load_configs_survives_unreadable_directory(tmp_path):
    """The `except OSError` branch: a directory that exists but cannot be listed."""
    unreadable = tmp_path / "locked"
    unreadable.mkdir(mode=0o000)
    try:
        assert load_configs(unreadable) == []
    finally:
        unreadable.chmod(0o755)


def test_load_configs_is_sorted_by_stem(tmp_path):
    for name in ("c", "a", "b"):
        (tmp_path / f"{name}.yaml").write_text("{}")
    assert [stem for stem, _ in load_configs(tmp_path)] == ["a", "b", "c"]


def test_load_configs_ignores_other_extensions(tmp_path):
    """A leftover .json from before the migration, or an editor's .yaml.bak,
    must not become a phantom config."""
    (tmp_path / "old.json").write_text('{"name": "stale"}')
    (tmp_path / "x.yaml.bak").write_text("name: stale\n")
    (tmp_path / "x.yml").write_text("name: stale\n")
    (tmp_path / "good.yaml").write_text("name: ok\n")
    assert load_configs(tmp_path) == [("good", {"name": "ok"})]


# --- the cache must never serve stale content ------------------------------


def test_cache_picks_up_an_edit(tmp_path):
    f = tmp_path / "x.yaml"
    f.write_text(yaml.safe_dump({"v": 1}))
    assert load_configs(tmp_path) == [("x", {"v": 1})]
    f.write_text(yaml.safe_dump({"v": 2}))
    assert load_configs(tmp_path) == [("x", {"v": 2})]


def test_cache_picks_up_add_and_delete(tmp_path):
    (tmp_path / "a.yaml").write_text("{}")
    assert [s for s, _ in load_configs(tmp_path)] == ["a"]
    (tmp_path / "b.yaml").write_text("{}")
    assert [s for s, _ in load_configs(tmp_path)] == ["a", "b"]
    (tmp_path / "a.yaml").unlink()
    assert [s for s, _ in load_configs(tmp_path)] == ["b"]


def test_cache_recovers_when_a_broken_file_is_repaired(tmp_path):
    f = tmp_path / "x.yaml"
    f.write_text(yaml.safe_dump({"v": 1}))
    assert load_configs(tmp_path) == [("x", {"v": 1})]
    f.write_text("{ broken")
    assert load_configs(tmp_path) == []
    f.write_text(yaml.safe_dump({"v": 3}))
    assert load_configs(tmp_path) == [("x", {"v": 3})]


def test_deleting_a_file_does_not_leak_into_a_reused_name(tmp_path):
    """A stale cache entry must not resurrect content under a recreated name."""
    f = tmp_path / "x.yaml"
    f.write_text(yaml.safe_dump({"v": "old"}))
    load_configs(tmp_path)
    f.unlink()
    assert load_configs(tmp_path) == []
    f.write_text(yaml.safe_dump({"v": "new"}))
    assert load_configs(tmp_path) == [("x", {"v": "new"})]
