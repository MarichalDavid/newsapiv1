from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

def canonical_url(u: str) -> str:
    if not u:
        return u
    s = urlsplit(u)
    q = [(k, v) for k, v in parse_qsl(s.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    return urlunsplit((s.scheme, s.netloc, s.path, urlencode(q), ""))
