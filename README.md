# igmk_api

Backend for the QuickLook-Browser &amp; WebDashboard
(frontend at `browser.herz-campaigns.de`).

## Requirements

Python 3.12+

## Run locally

```bash
pip3 install -r requirements-dev.txt
IGMK_CONFIG_ROOT=./config uvicorn igmk_api.app:app
```

`IGMK_CONFIG_ROOT` points the app at the config tree. It defaults to `/config`,
which is where production bind-mounts it; setting it to the checked-in dev copy
means **no source edits are needed for local development**. Use
`uvicorn igmk_api.app:app --reload` for hot-reloading.

| Variable | Default | Purpose |
|---|---|---|
| `IGMK_CONFIG_ROOT` | `/config` | Config tree: `plots/`, `instruments/`, `sites/` |
| `IGMK_CORS_ORIGINS` | `https://browser.herz-campaigns.de` | Comma-separated allowed origins |

The API is then available at:

```
http://localhost:8000/ui/        # interactive Swagger UI
http://localhost:8000/openapi.json   # the raw spec
```

(Note: the spec is served at `/openapi.json`, not `/swagger.json`.)

## Tests and linting

```bash
pytest         # runs against tests/fixtures/config, not the real config tree
ruff check .
```

## Docker

```YAML
version: "3.8"

services:
  api:
    image: ghcr.io/igmk/api:latest
    container_name: api
    volumes:
      - /data/obs/api_config/default:/config:ro
      - /data/obs:/data/obs:ro
    ports:
      - "8000:8000"
    restart: unless-stopped
```

## Resilience

Config files are operational data, so a broken one never takes the service down:
an unreadable, malformed or non-object JSON file is logged at `WARNING` and
skipped, and a missing config directory yields an empty result rather than a
500. An unknown identifier, or a plot image that does not exist for the
requested date, is a `404` with a JSON body. See `igmk_api/config.py` and
`tests/test_resilience.py`.

Parsed configs are cached in each worker and revalidated against every file's
modification time on each request, so editing, adding or removing a config takes
effect immediately -- no restart, and no stale window.

## Config files

Production config lives at:

```
/data/obs/api_config
```

A copy for development is checked in at `config/`.
