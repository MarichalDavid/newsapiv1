import httpx
from ..core.config import settings

def client():
    return httpx.Client(follow_redirects=True, headers={
        "User-Agent": settings.USER_AGENT,
        "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8"
    }, timeout=15.0)
