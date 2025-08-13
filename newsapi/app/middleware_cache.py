
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.requests import Request
import hashlib, asyncio, os
from redis.asyncio import Redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
API_CACHE_TTL_SECONDS = int(os.getenv("API_CACHE_TTL_SECONDS", "30"))
redis = Redis.from_url(REDIS_URL, decode_responses=True)

def _key(path:str, query:str)->str:
    return "api:" + hashlib.sha1(f"{path}?{query}".encode()).hexdigest()

class RedisGetCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "GET" and request.url.path.startswith("/api"):
            k = _key(request.url.path, request.url.query)
            try:
                cached = await redis.get(k)
                if cached:
                    return Response(cached, media_type="application/json")
            except Exception:
                pass
            response = await call_next(request)
            if response.status_code == 200 and response.media_type == "application/json":
                body = await response.body()
                try:
                    await redis.set(k, body.decode("utf-8"), ex=API_CACHE_TTL_SECONDS)
                except Exception:
                    pass
                return Response(body, media_type="application/json", status_code=200)
            return response
        return await call_next(request)
