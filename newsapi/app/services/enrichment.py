from typing import Dict, Any
import trafilatura
from ..utils.http import client

def enrich_html(url: str) -> Dict[str, Any]:
    with client() as c:
        r = c.get(url, headers={"Accept": "text/html, */*"})
        r.raise_for_status()
        text = trafilatura.extract(r.text, include_images=False, include_formatting=False, include_links=False, output_format="txt")
    return {"full_text": text or None, "jsonld": None}
