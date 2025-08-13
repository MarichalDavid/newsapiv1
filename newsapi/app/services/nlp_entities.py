import spacy
from functools import lru_cache
from typing import Dict, List

@lru_cache(maxsize=2)
def _nlp(lang: str):
    try:
        if (lang or '').startswith("fr"):
            return spacy.load("fr_core_news_sm")
        return spacy.load("en_core_web_sm")
    except Exception:
        return spacy.blank("fr" if (lang or '').startswith("fr") else "en")

def extract_entities(text: str, lang: str = "en") -> Dict[str, List[str]]:
    if not text:
        return {}
    nlp = _nlp(lang or "en")
    doc = nlp(text)
    out: Dict[str, List[str]] = {}
    for ent in doc.ents:
        out.setdefault(ent.label_, [])
        if ent.text not in out[ent.label_]:
            out[ent.label_].append(ent.text)
    return out
