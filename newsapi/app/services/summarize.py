from __future__ import annotations

import os
import re
from typing import Optional, Tuple

# --------------------------------------------------------------------------------------
# Choix de résumé basique (utilisé par le collector)
# --------------------------------------------------------------------------------------

def _limit_words(txt: str | None, max_words: int) -> str | None:
    if not txt:
        return None
    words = re.findall(r"\S+", txt)
    if len(words) <= max_words:
        return txt.strip()
    return " ".join(words[:max_words]).strip()

def choose_summary(
    summary_feed: Optional[str],
    full_text: Optional[str],
    *,
    max_words_feed: int = 120,
    max_words_llm: int = 160
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Renvoie (summary_final, summary_source, summary_llm).

    - Si le flux fournit déjà un résumé utilisable, on le préfère (summary_source='feed').
    - Sinon, on laisse summary_final=None -> la route /summaries pourra appeler le LLM
      et persister le résultat (summary_source='llm').
    """
    s_feed = _limit_words(summary_feed, max_words_feed)
    if s_feed:
        return (s_feed, "feed", None)

    # Pas de feed: on signalera à la route de générer au LLM
    return (None, None, None)

# --------------------------------------------------------------------------------------
# Appel LLM (Ollama) pour résumer / synthétiser
# --------------------------------------------------------------------------------------

import httpx  # nécessite httpx installé dans l'image

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

async def _ollama_generate(prompt: str) -> str:
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        return (data.get("response") or "").strip()

async def llm_summarize(
    text: str,
    *,
    lang: str | None = None,
    max_words: int = 160,
    style: str | None = None
) -> str:
    """
    Résume 'text' avec Ollama. Fallback : tronque si l'appel LLM échoue.
    """
    lang = (lang or "fr").strip()
    style = (style or "factuel, neutre, concis").strip()

    system = (
        f"Tu es un assistant qui rédige un résumé {style} en {lang}. "
        f"Limite-toi à {max_words} mots, pas de listes à puces si ce n'est pas demandé."
    )
    prompt = f"{system}\n\nTexte à résumer :\n{text.strip()}\n"

    try:
        out = await _ollama_generate(prompt)
        if not out:
            return (_limit_words(text, max_words) or "").strip()
        # Sécurité : re-troncature au cas où
        return (_limit_words(out, max_words) or out).strip()
    except Exception:
        return (_limit_words(text, max_words) or "").strip()

async def llm_synthesis_from_docs(
    docs: list[dict],
    *,
    lang: str = "fr",
    max_words: int = 260
) -> str:
    """
    Construit une synthèse multi-documents.
    Chaque doc attendu: {"title":..., "summary":..., "url":..., "published_at":...}
    """
    parts: list[str] = []
    for d in docs:
        title = (d.get("title") or "(untitled)").strip()
        summ  = (d.get("summary") or "").strip()
        url   = d.get("url") or ""
        dt    = d.get("published_at")
        dt_s  = str(dt) if dt else ""
        line  = f"- {dt_s} | {title}\n  {summ}\n  {url}"
        parts.append(line)

    corpus = "\n".join(parts) if parts else "(aucun document)"
    prompt = (
        f"Tu es journaliste. Fais une synthèse claire et structurée (max {max_words} mots) "
        f"à partir de plusieurs articles, en {lang}. Donne :\n"
        f"1) Les 4-7 points clés (phrases courtes)\n"
        f"2) Le contexte/tendance\n"
        f"3) S'il y a controverse ou incertitude, dis-le\n"
        f"4) Finis par 2-4 sources les plus pertinentes (titre court + domaine)\n\n"
        f"Corpus:\n{corpus}\n"
    )
    try:
        return await _ollama_generate(prompt)
    except Exception:
        # fallback basique: concat’ de titres
        return "\n".join(["• " + (d.get("title") or "(untitled)") for d in docs[:8]])
