from typing import Dict, Any
from ..utils.http import client
from .facts import extract_facts

# ✅ IMPORT CONDITIONNEL: trafilatura avec fallback
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    print("⚠️ trafilatura not available, using fallback extraction")

def enrich_html(url: str) -> Dict[str, Any]:
    """Enrichit une URL en extrayant le contenu HTML"""
    try:
        with client() as c:
            r = c.get(url, headers={"Accept": "text/html, */*"})
            r.raise_for_status()
            
            if TRAFILATURA_AVAILABLE:
                # ✅ Utilisation de trafilatura si disponible
                text = trafilatura.extract(
                    r.text, 
                    include_images=False, 
                    include_formatting=False, 
                    include_links=False, 
                    output_format="txt"
                )
            else:
                # ✅ FALLBACK: Extraction basique avec BeautifulSoup
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(r.text, 'html.parser')
                    
                    # Supprime les scripts et styles
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    # Extrait le texte principal
                    text = soup.get_text()
                    
                    # Nettoie le texte
                    lines = (line.strip() for line in text.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    text = ' '.join(chunk for chunk in chunks if chunk)
                    
                except ImportError:
                    # ✅ FALLBACK ULTIME: Extraction très basique
                    import re
                    # Supprime les balises HTML basiques
                    text = re.sub(r'<[^>]+>', '', r.text)
                    # Nettoie les espaces multiples
                    text = re.sub(r'\s+', ' ', text).strip()
            
            # Extract facts from the content
            facts = extract_facts(text) if text else []
            
            return {
                "full_text": text or None, 
                "jsonld": None,
                "facts": facts
            }
            
    except Exception as e:
        print(f"[enrichment] Error enriching {url}: {e}")
        return {"full_text": None, "jsonld": None, "facts": []}