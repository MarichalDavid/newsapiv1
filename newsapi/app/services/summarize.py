from __future__ import annotations

import os
import re
import logging
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

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
    s_feed = _limit_words(summary_feed, max_words_feed)
    if s_feed:
        return (s_feed, "feed", None)
    return (None, None, None)

# --------------------------------------------------------------------------------------
# Appel LLM (Ollama) pour résumer / synthétiser
# --------------------------------------------------------------------------------------

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

async def _ollama_generate(prompt: str) -> str:
    """Optimized Ollama generation with aggressive timeouts"""
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt[:4000],  # Much shorter context for speed
        "stream": False,
        "options": {
            "temperature": 0.1,  # Lower for faster generation
            "num_ctx": 2048,  # Even smaller context window
            "num_predict": 150,  # Limit output tokens more
            "top_p": 0.8,
            "repeat_penalty": 1.05,
        },
    }
    try:
        # Very aggressive timeout for synthesis endpoints
        async with httpx.AsyncClient(timeout=8.0) as client:  # Only 8 seconds max
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            response = (data.get("response") or "").strip()
            if not response:
                logger.warning("Empty LLM response, using fallback")
                return ""
            return response
    except (httpx.RequestError, httpx.HTTPStatusError, httpx.TimeoutException) as e:
        logger.warning(f"LLM timeout/error, using fallback: {str(e)[:50]}")
        return ""  # Return empty to trigger fallback
    except Exception as e:
        logger.error(f"Unexpected LLM error: {e}")
        return ""

async def llm_summarize(
    text: str,
    *,
    lang: str | None = None,
    max_words: int = 160,
    style: str | None = None
) -> str:
    lang = (lang or "fr").strip()
    style = (style or "factuel, neutre, concis").strip()
    system = (
        f"Tu es un assistant qui rédige un résumé {style} en {lang}. "
        f"Limite-toi à {max_words} mots, pas de listes à puces si ce n'est pas demandé."
    )
    prompt = f"{system}\n\nTexte à résumer :\n{text.strip()}\n"

    out = await _ollama_generate(prompt)
    if not out:
        return (_limit_words(text, max_words) or "").strip()
    return (_limit_words(out, max_words) or out).strip()

def create_basic_synthesis(docs: list[dict], lang: str = "fr", max_words: int = 260) -> str:
    """Create a fast, rule-based synthesis when LLM fails or times out"""
    if not docs:
        return "No articles found for synthesis."
    
    # Extract key information
    domains = {}
    topics = []
    
    for d in docs:
        domain = d.get("domain", "unknown")
        domains[domain] = domains.get(domain, 0) + 1
        
        title = d.get("title", "")
        if title:
            # Simple keyword extraction
            words = title.lower().split()
            for word in words:
                if len(word) > 4 and word not in ['news', 'article', 'breaking']:
                    topics.append(word)
    
    # Build synthesis
    synthesis_parts = []
    
    if lang == "fr":
        synthesis_parts.append(f"**Synthèse de {len(docs)} articles récents**")
        synthesis_parts.append(f"Sources principales: {', '.join(list(domains.keys())[:3])}")
    else:
        synthesis_parts.append(f"**Synthesis of {len(docs)} recent articles**")
        synthesis_parts.append(f"Main sources: {', '.join(list(domains.keys())[:3])}")
    
    # Add top articles
    synthesis_parts.append("")
    for i, d in enumerate(docs[:5], 1):
        title = d.get("title", "Untitled")
        domain = d.get("domain", "")
        synthesis_parts.append(f"{i}. {title} ({domain})")
    
    result = "\n".join(synthesis_parts)
    return _limit_words(result, max_words) or result

async def llm_synthesis_from_docs(
    docs: list[dict],
    *,
    lang: str = "fr",
    max_words: int = 260
) -> str:
    # Quick fallback for empty docs
    if not docs:
        return "No articles available for synthesis."
    
    # If too many docs, use only the most recent ones for speed
    if len(docs) > 10:
        docs = docs[:10]
    
    # Build a shorter, more focused prompt
    titles = []
    for d in docs[:8]:  # Limit to 8 articles max for speed
        title = (d.get("title") or "").strip()
        domain = d.get("domain") or ""
        if title:
            titles.append(f"• {title} ({domain})")
    
    if not titles:
        return create_basic_synthesis(docs, lang, max_words)
    
    # Much shorter prompt for speed
    corpus = "\n".join(titles)
    prompt = (
        f"Synthesize these {len(titles)} news articles in {lang} "
        f"(max {max_words//2} words):\n{corpus}\n\n"
        f"Give main trends and key points:"
    )

    # Try LLM with timeout
    try:
        out = await _ollama_generate(prompt)
        if out and len(out.strip()) > 10:  # Valid response
            return _limit_words(out.strip(), max_words) or out.strip()
    except Exception as e:
        logger.warning(f"LLM synthesis failed: {e}")
    
    # Fallback to rule-based synthesis
    logger.info("Using fallback synthesis due to LLM timeout/failure")
    return create_basic_synthesis(docs, lang, max_words)
