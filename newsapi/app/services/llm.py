import os
import httpx
import logging
import json

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

logger = logging.getLogger(__name__)

async def generate_llm(prompt: str, max_tokens: int = 256, temperature: float = 0.2) -> str:
    """
    Appelle Ollama /api/generate (non-stream) et renvoie le texte généré.
    Optimisé pour Qwen2.5:3B avec timeouts adaptés.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt[:8000],  # Reduced context for faster processing
        "stream": False,
        "options": {
            "num_ctx": 4096,  # Reduced context window
            "num_predict": min(max_tokens, 256),  # Limit output tokens
            "temperature": temperature,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:  # Reduced timeout
            response = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
    except httpx.RequestError as e:
        logger.error(f"Erreur HTTP lors de l'appel à Ollama: {e}")
        return f"Error: Connection failed - {str(e)[:100]}"
    except httpx.HTTPStatusError as e:
        logger.error(f"Erreur de statut HTTP: {e.response.status_code} - {e.response.text}")
        return f"Error: HTTP {e.response.status_code}"
    except Exception as e:
        logger.error(f"Erreur inconnue lors de l'appel à Ollama: {e}")
        return f"Error: {str(e)[:100]}"

async def generate_llm_stream(prompt: str):
    """Optimized streaming version for Qwen2.5:3B"""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt[:8000],  # Reduced context
        "stream": True,
        "options": {"num_ctx": 4096, "num_predict": 256, "temperature": 0.2}
    }

    text = ""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", f"{OLLAMA_BASE_URL}/api/generate", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        text += chunk.get("response", "")
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        pass
        return text.strip()
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        return f"Error: {str(e)[:100]}"
