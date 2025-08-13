import feedparser
from typing import Iterable, Dict, Any, Optional
from ..utils.http import client

def fetch_feed(url: str, etag: Optional[str]=None, last_modified: Optional[str]=None):
    headers = {}
    if etag: headers["If-None-Match"] = etag
    if last_modified: headers["If-Modified-Since"] = last_modified
    with client() as c:
        r = c.get(url, headers=headers)
        status = r.status_code
        return status, r

def parse_feed(content: bytes) -> Iterable[Dict[str, Any]]:
    fp = feedparser.parse(content)
    for e in fp.entries:
        yield {
            "title": e.get("title"),
            "link": e.get("link"),
            "summary": e.get("summary") or e.get("description"),
            "published": e.get("published") or e.get("updated"),
            "authors": [a.get("name") for a in e.get("authors", [])] if e.get("authors") else None,
            "raw": e
        }
