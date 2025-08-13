
POS = {"good","great","up","gain","positive","win","success"}
NEG = {"bad","down","loss","negative","fail","breach","attack"}

def label_text(text: str | None):
    if not text:
        return "neu", 0.0
    t = text.lower()
    pos = sum(w in t for w in POS)
    neg = sum(w in t for w in NEG)
    score = (pos - neg) / max(1, pos + neg)
    if score > 0.2: return ("pos", float(score))
    if score < -0.2: return ("neg", float(score))
    return ("neu", 0.0)
