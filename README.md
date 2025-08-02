# Caching Proxy Server

A lightweight Python-based proxy server that **forwards client requests to an origin server and caches the responses** to improve performance and reduce load.

Built with:
- **FastAPI** – HTTP server & routing
- **httpx** – forwarding requests
- **Redis (Upstash)** – caching layer
- **argparse** – CLI interface
- **uvicorn** - ASGI server

---

## Features
- CLI to start the proxy server:
  - `--port` → specify the port to run on
  - `--origin` → specify the origin server URL
- Transparent caching of HTTP GET responses
- Supports cache revalidation with `ETag` and `Last-Modified`
- Respects standard HTTP cache headers:
  - `Cache-Control`
  - `Expires`
  - etc.
- Clear entire cache easily using `--clear-cache`
- Adds custom response header:
  - `X-Cache: HIT` → response served from cache
  - `X-Cache: MISS` → fresh response fetched and cached

---

## Usage

#### Commands
This command starts the listening at the specified port on local host.
```python
python proxy.py --port <number> --origin <url>
```

clear-cache command clears the cache (i.e. Deletes everthing from the cache).
```
python proxy.py --clear-cache
```


## Screenshots

```
python proxy.py --port 8000 --origin  https://www.python-httpx.org/
```
![alt text](<assests/images/Screenshot (70).png>)

- upstash cache storage 
![alt text](<assests/images/Screenshot (71).png>)

- resources being fetced from cache.
![alt text](<assests/images/Screenshot (72).png>)