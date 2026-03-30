# igmk_api
Backend for new QL-Browser &amp; WebDashboard

## Requirements
Python 3.5.2+


## Usage

## Run local (only for dev)
To run the server, please execute the following from the root directory:

```
pip3 install -r requirements.txt
cd app
uvicorn run:app
```
- adjust all `/config` paths in `app/run.py` (remember to undo this change beofore commiting to github)
- For development purposes, you can use `uvicorn run:app --reload` for hot-reloading.

API is available at:
```
http://localhost:8080/ui/
```

Your Swagger definition lives here:

```
http://localhost:8080/swagger.json
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

## Config Files

All Config Files for the API are stored at:

```
/data/obs/api_config
```
