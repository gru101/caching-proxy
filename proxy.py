import httpx
from fastapi import FastAPI, responses
from dotenv import load_dotenv
import os 
from upstash_redis import Redis
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
import datetime
import argparse
import uvicorn

load_dotenv(dotenv_path=".env")
UPSTASH_REDIS_URL= os.getenv("UPSTASH_REDIS_URL")
UPSTASH_REDIS_KEY = os.getenv("UPSTASH_REDIS_TOKEN")

if UPSTASH_REDIS_URL is not None and UPSTASH_REDIS_KEY is not None:
    redis = Redis(url=UPSTASH_REDIS_URL, token=UPSTASH_REDIS_KEY)
    print("Redis Connection Established.")

origin_server = str
app = FastAPI()

def store_in_cache(url, response):
    headers = dict(response.headers)
    value = {
        "content": response.content.decode('utf-8', errors='ignore'),
        "headers": headers,
        "status_code": response.status_code
    }
    result = redis.json.set(key=url, path="$", value=value)
    return result

def set_expiry(url, response):
    headers = dict(response.headers)
    cache_control = headers.get("cache-control", "").lower().split(",")
    expires = headers.get("expires")
    smaxage = None
    maxage = None

    # parse cache-control
    for direc in cache_control:
        parts = direc.strip().split("=")
        if len(parts) == 2:
            key, value = parts
            if key == "s-maxage":
                smaxage = int(value)
            elif key == "max-age":
                maxage = int(value)

    if "no-store" in cache_control or "private" in cache_control:
        print("Resource cannot be cached")
        return
    else:
        store_in_cache(url, response)
        if smaxage:
            redis.expire(key=url, seconds=smaxage)
        elif maxage:
            redis.expire(key=url, seconds=maxage)
        elif expires:
            try:
                expires_datetime = parsedate_to_datetime(expires)
                now = datetime.now(timezone.utc)
                ttl = (expires_datetime - now).total_seconds()
                if ttl > 0:
                    redis.expire(key=url, seconds=int(ttl))
            except Exception as e:
                print("Invalid Expires header:", e)
                
def get_cached_resource(url):
    cached = redis.json.get(key=url)
    if cached and cached != [None]:
        cached = cached[0]
        headers = cached["headers"]
        cache_control = headers.get("cache-control", "").lower().split(",")

        revalidate = "must-revalidate" in [c.strip() for c in cache_control]
        etag = headers.get("etag")
        last_modified = headers.get("last-modified")

        with httpx.Client() as client:
            if revalidate and (etag or last_modified):
                req_headers = {}
                if etag:
                    req_headers["If-None-Match"] = etag
                if last_modified:
                    req_headers["If-Modified-Since"] = last_modified

                server_response = client.get(url, headers=req_headers)

                if server_response.status_code == 304:
                    print("Resource not modified, serve cached.")
                    return cached
                else:
                    print("Resource updated on origin, update cache.")
                    meta = parse_cache_headers(server_response.headers)
                    store_in_cache(url, server_response)
                    return {
                        "content": server_response.content.decode('utf-8', errors='ignore'),
                        "headers": dict(server_response.headers),
                        "status_code": server_response.status_code,
                        "cache_meta": {
                            **meta,
                            "stored_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
            else:
                print("No revalidate needed, serve cached.")
                return cached
    else:
        return None

@app.get("/{full_path:path}")
def proxy(full_path: str):
    url = f"{origin_server.rstrip('/')}/{full_path}"
    print(f"Proxy request for: {url}")

    cached = get_cached_resource(url)
    if cached:
        print("Cache HIT")
        return responses.Response(
            content=cached["content"],
            media_type=cached["headers"].get("content-type"),
            status_code=cached["status_code"],
            headers={"X-Cache": "HIT"}
        )

    with httpx.Client() as client:
        response = client.get(url)
        set_expiry(url, response)

    return responses.Response(
        content=response.content,
        media_type=response.headers.get("content-type"),
        status_code=response.status_code,
        headers={"X-Cache": "MISS"}
    )

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, help="port number on which the service should run on.",default=8000)
parser.add_argument('--origin', type=str, help="address of the website or server.")
parser.add_argument('--clear-cache', action="store_true")
args = parser.parse_args()

if args.clear_cache:
    redis.flushall()
    print("Cache Cleared")
    exit(0)

if not args.origin:
    print("origin server addresss is required")
    exit(1)

origin_server = args.origin

if __name__ == '__main__':
    uvicorn.run("proxy:app", host="0.0.0.0", port=args.port, reload=True)
