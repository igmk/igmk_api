# igmk_api
Backend for new QL-Browser &amp; WebDashboard

## Requirements
Python 3.5.2+


## Usage
To run the server, please execute the following from the root directory:

```
pip3 install -r requirements.txt
cd app
uvicorn run:app
```
For development purposes, you can use `uvicorn run:app --reload` for hot-reloading.
and open your browser to here:

```
http://localhost:8080/ui/
```

Your Swagger definition lives here:

```
http://localhost:8080/swagger.json
```
## Docker
```BASH
docker run -p 8000:8000 ghcr.io/igmk/api:latest
```

## Config Files

All Config Files for the API are stored at:

```
/data/obs/api_config
```
