import re

RULES = {
    "acquire": ["acquire","buy","purchase"],
    "announce": ["announce","launch","introduce"],
    "accuse": ["accuse","blame"],
    "sanction": ["sanction"],
    "meet": ["meet","met","meeting"]
}

def sentence_split(text: str | None):
    if not text:
        return []
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s and s.strip()]

def extract_facts(text: str | None):
    """Heuristique minimaliste : détecte des relations lexicales entre (éventuelles) entités.
    Retourne une liste de dicts avec subj/obj si trouvés, sinon None.
    """
    if not text:
        return []
    facts = []
    for i, sent in enumerate(sentence_split(text)):
        st = sent.lower()
        # entités candidates : suites de Mots Capitalisés (PERSON/ORG approximatif)
        ents = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b", sent)
        for rel, keys in RULES.items():
            if any(k in st for k in keys):
                if len(ents) >= 2:
                    facts.append({
                        "subj": ents[0],
                        "rel": rel,
                        "obj": ents[1],
                        "confidence": 0.4,
                        "sentence_idx": i
                    })
                else:
                    facts.append({
                        "subj": None,
                        "rel": rel,
                        "obj": None,
                        "confidence": 0.2,
                        "sentence_idx": i
                    })
    return facts
