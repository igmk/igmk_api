"""The openapi.yaml <-> handler handshake.

The whole architecture rests on this contract: openapi.yaml declares every route
and binds it to a function via ``operationId``. If the two drift, a route 404s
or the app fails to start. These tests make that drift a test failure instead of
a production surprise.
"""

import importlib
import inspect
import re

import pytest
import yaml
from igmk_api.app import SPEC_PATH

SPEC = yaml.safe_load(SPEC_PATH.read_text())

#: Modules that hold routed handlers.
HANDLER_MODULES = [
    "igmk_api.api.general",
    "igmk_api.api.sites",
    "igmk_api.api.instruments",
    "igmk_api.api.plots",
    "igmk_api.api.search",
]

PATH_PARAM_RE = re.compile(r"\{([^}]+)\}")


def _operations():
    """Yield (path, method, operation) for every operation in the spec."""
    for path, item in SPEC["paths"].items():
        for method, operation in item.items():
            if method in {"get", "post", "put", "patch", "delete", "head", "options"}:
                yield path, method, operation


def _operation_ids():
    return [op["operationId"] for _, _, op in _operations()]


def _resolve(operation_id):
    module_name, _, func_name = operation_id.rpartition(".")
    return getattr(importlib.import_module(module_name), func_name)


def test_spec_has_paths():
    assert SPEC["paths"], "spec declares no paths"


@pytest.mark.parametrize("operation_id", _operation_ids())
def test_operation_id_resolves(operation_id):
    """Every operationId points at an importable, callable function."""
    func = _resolve(operation_id)
    assert callable(func), f"{operation_id} is not callable"


def test_operation_ids_are_unique():
    ids = _operation_ids()
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert not duplicates, f"operationId reused across paths: {sorted(duplicates)}"


def test_every_public_handler_is_routed():
    """Catches dead handlers and renames that only got applied on one side.

    A public function in a handler module that no operationId references is
    either dead code or a route that silently stopped existing.
    """
    routed = {oid.rpartition(".")[2] for oid in _operation_ids()}
    unrouted = []
    for module_name in HANDLER_MODULES:
        module = importlib.import_module(module_name)
        for name, obj in vars(module).items():
            if name.startswith("_") or not inspect.isfunction(obj):
                continue
            if obj.__module__ != module_name:  # imported, not defined here
                continue
            if name not in routed:
                unrouted.append(f"{module_name}.{name}")
    # create_map_javascript is deliberately internal: map_redirect calls it.
    assert unrouted == ["igmk_api.api.general.create_map_javascript"], (
        f"handlers defined but not routed: {unrouted}"
    )


@pytest.mark.parametrize("operation_id", _operation_ids())
def test_handler_signature_matches_path_params(operation_id):
    """A handler must accept every parameter its path template declares."""
    path = next(p for p, _, op in _operations() if op["operationId"] == operation_id)
    declared = set(PATH_PARAM_RE.findall(path))
    accepted = set(inspect.signature(_resolve(operation_id)).parameters)
    missing = declared - accepted
    assert not missing, f"{operation_id} does not accept path params {sorted(missing)}"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "openapi.yaml declares zero `parameters:` blocks for its 11 parameterised "
        "routes, so Connexion does no type coercion or validation and Swagger UI "
        "renders no input boxes. Scheduled for the spec-repair round; this test "
        "flips to passing for free once parameters land."
    ),
)
def test_path_params_are_declared():
    """Every {param} in a path template has a matching `parameters` entry."""
    undeclared = []
    for path, method, operation in _operations():
        declared = {
            p["name"] for p in operation.get("parameters", []) if p.get("in") == "path"
        }
        for name in PATH_PARAM_RE.findall(path):
            if name not in declared:
                undeclared.append(f"{method.upper()} {path} -> {name}")
    assert not undeclared, f"path params with no `parameters` entry: {undeclared}"
