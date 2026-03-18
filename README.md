# igmk_api
Backend for new QL-Browser &amp; WebDashboard

## Requirements
Python 3.5.2+

## Usage
To run the server, please execute the following from the root directory:

```
pip3 install -r requirements.txt
python3 -m swagger_server
```

and open your browser to here:

```
http://localhost:8080/ui/
```

Your Swagger definition lives here:

```
http://localhost:8080/swagger.json
```
## Docker
Future implementation as a docker container.
```
docker build -t igmk_api .
```
```
version: "3.8"
services:
  igmk_api:
    image: igmk_api
    container_name: igmk_api
    restart: unless-stopped
    volumes:
      - ./igmk_api:/data
    ports:
      - 80:80
```

## Config Files

All Config Files for the API are stored at:

```
/data/obs/api_config
```
