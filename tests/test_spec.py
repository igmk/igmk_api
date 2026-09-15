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
    assert unrouted == [], f"handlers defined but not routed: {unrouted}"


@pytest.mark.parametrize("operation_id", _operation_ids())
def test_handler_signature_matches_path_params(operation_id):
    """A handler must accept every parameter its path template declares."""
    path = next(p for p, _, op in _operations() if op["operationId"] == operation_id)
    declared = set(PATH_PARAM_RE.findall(path))
    accepted = set(inspect.signature(_resolve(operation_id)).parameters)
    missing = declared - accepted
    assert not missing, f"{operation_id} does not accept path params {sorted(missing)}"


def _resolve_ref(node):
    """Follow a single ``$ref`` into the spec, if this node is one."""
    ref = node.get("$ref")
    if not ref:
        return node
    target = SPEC
    for part in ref.removeprefix("#/").split("/"):
        target = target[part]
    return target


def test_path_params_are_declared():
    """Every {param} in a path template has a matching `parameters` entry.

    Without these Connexion does no coercion or validation and Swagger UI
    renders no input boxes.
    """
    undeclared = []
    for path, method, operation in _operations():
        declared = {
            p["name"]
            for p in map(_resolve_ref, operation.get("parameters", []))
            if p.get("in") == "path"
        }
        for name in PATH_PARAM_RE.findall(path):
            if name not in declared:
                undeclared.append(f"{method.upper()} {path} -> {name}")
    assert not undeclared, f"path params with no `parameters` entry: {undeclared}"


def test_path_params_are_typed():
    """A declared path param without a schema still does no validation."""
    untyped = []
    for path, method, operation in _operations():
        for p in map(_resolve_ref, operation.get("parameters", [])):
            if p.get("in") == "path" and not p.get("schema"):
                untyped.append(f"{method.upper()} {path} -> {p['name']}")
    assert not untyped, f"path params with no `schema`: {untyped}"


def test_error_statuses_are_json():
    """Handlers return {"error": ...} bodies; the spec must declare them.

    When a route declared only image/png, Connexion serialised the dict against
    that content type and the client received the literal string "error".
    """
    missing = []
    for path, method, operation in _operations():
        for status, response in operation["responses"].items():
            if not status.startswith(("4", "5")):
                continue
            response = _resolve_ref(response)
            if "application/json" not in response.get("content", {}):
                missing.append(f"{method.upper()} {path} -> {status}")
    assert not missing, f"error responses that are not JSON: {missing}"


def test_components_are_all_referenced():
    """An unreferenced component is dead weight in the contract."""
    text = SPEC_PATH.read_text()
    orphans = [
        f"{section}/{name}"
        for section in ("schemas", "parameters", "responses")
        for name in SPEC.get("components", {}).get(section, {})
        if text.count(f"#/components/{section}/{name}") == 0
    ]
    assert not orphans, f"components never referenced: {orphans}"


def test_no_inline_response_duplicates_a_component():
    """Catches a response block that should have been a $ref."""
    components = {
        name: response
        for name, response in SPEC.get("components", {}).get("responses", {}).items()
    }
    duplicates = []
    for path, method, operation in _operations():
        for status, response in operation["responses"].items():
            if "$ref" in response:
                continue
            for name, component in components.items():
                if response == component:
                    duplicates.append(f"{method.upper()} {path} {status} == {name}")
    assert not duplicates, f"inline responses that duplicate a component: {duplicates}"


def test_spec_is_valid_openapi():
    openapi_spec_validator = pytest.importorskip("openapi_spec_validator")
    openapi_spec_validator.validate(SPEC)
