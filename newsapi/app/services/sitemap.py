from typing import List, Dict, Optional
from lxml import etree
from ..utils.http import client

NS = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

def fetch_xml(url: str) -> Optional[bytes]:
    try:
        with client() as c:
            r = c.get(url, headers={"Accept":"application/xml, text/xml;q=0.9, */*;q=0.8"})
            if r.status_code >= 400: 
                return None
            return r.content
    except Exception:
        return None

def discover_from_sitemap(base: str, limit: int = 50) -> List[Dict]:
    urls_to_try = [f"https://{base}/sitemap.xml", f"http://{base}/sitemap.xml"]
    locs = []
    for u in urls_to_try:
        xml = fetch_xml(u)
        if not xml: 
            continue
        try:
            root = etree.fromstring(xml)
            sitemaps = root.findall(".//sm:sitemap/sm:loc", namespaces=NS)
            if sitemaps:
                for sm in sitemaps[:5]:
                    sub = fetch_xml(sm.text.strip())
                    if not sub: 
                        continue
                    subroot = etree.fromstring(sub)
                    for loc in subroot.findall(".//sm:url/sm:loc", namespaces=NS)[:limit]:
                        locs.append({"url": loc.text.strip()})
            else:
                for loc in root.findall(".//sm:url/sm:loc", namespaces=NS)[:limit]:
                    locs.append({"url": loc.text.strip()})
        except Exception:
            continue
        if locs:
            break
    return locs[:limit]
