import yake

def extract_keywords(text: str, lang: str = "en", topk: int = 12):
    if not text:
        return None
    lan = lang if lang in {"en","fr","ar"} else "en"
    kw_extractor = yake.KeywordExtractor(lan=lan, n=3, top=topk)
    kws = [k for k,_ in kw_extractor.extract_keywords(text)]
    seen = set(); out = []
    for k in kws:
        kl = k.lower()
        if kl not in seen and len(kl) >= 4:
            seen.add(kl); out.append(k)
    return out[:topk]
