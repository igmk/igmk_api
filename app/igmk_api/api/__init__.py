"""HTTP handlers, one module per OpenAPI tag.

Every public function here is bound to a route by an ``operationId`` in
``igmk_api/openapi.yaml``. Adding an endpoint means adding a function *and* a
path item; renaming one means renaming both.
"""
