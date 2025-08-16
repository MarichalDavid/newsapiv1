import feedparser
from typing import Iterable, Dict, Any, Optional
from ..utils.http import client

def fetch_feed(url: str, etag: Optional[str]=None, last_modified: Optional[str]=None):
    """Récupère un feed RSS/Atom avec gestion des headers conditionnels"""
    headers = {}
    if etag: 
        headers["If-None-Match"] = etag
    if last_modified: 
        headers["If-Modified-Since"] = last_modified
    
    try:
        with client() as c:
            r = c.get(url, headers=headers, timeout=30)
            status = r.status_code
            return status, r
    except Exception as e:
        print(f"[discovery] Error fetching feed {url}: {e}")
        return 500, None

def parse_feed(content) -> Iterable[Dict[str, Any]]:
    """Parse le contenu d'un feed RSS/Atom avec gestion robuste des erreurs"""
    try:
        # 🔧 CORRECTION: Gestion robuste du contenu (bytes ou string)
        if hasattr(content, 'decode'):
            # Si c'est des bytes
            content_str = content.decode('utf-8', errors='ignore')
        elif hasattr(content, 'encode'):
            # Si c'est déjà une string
            content_str = content
        else:
            # Si c'est autre chose, convertir en string
            content_str = str(content)
        
        # 🔧 CORRECTION: Parse avec feedparser et gestion d'erreur robuste
        fp = feedparser.parse(content_str)
        
        # Vérification des erreurs de parsing
        if fp.bozo and hasattr(fp, 'bozo_exception'):
            print(f"[discovery] Feed parsing warning: {fp.bozo_exception}")
        
        # 🔧 CORRECTION: Vérification que fp.entries existe
        if not hasattr(fp, 'entries') or not fp.entries:
            print("[discovery] No entries found in feed")
            return []
        
        # Extraction robuste des entrées
        for e in fp.entries:
            # 🔧 CORRECTION: Validation que e est un objet avec des attributs
            if not hasattr(e, 'get'):
                continue
                
            # Extraction avec gestion des champs manquants
            entry = {
                "title": (e.get("title", "") or "").strip() or None,
                "link": (e.get("link", "") or "").strip() or None,
                "summary": (
                    e.get("summary", "") or 
                    e.get("description", "") or 
                    ""
                ).strip() or None,
                "published": (
                    e.get("published") or 
                    e.get("updated") or 
                    e.get("pubDate")
                ),
                "authors": None,
                "raw": e
            }
            
            # 🔧 CORRECTION: Traitement robuste des auteurs
            try:
                if e.get("authors"):
                    authors = []
                    for a in e.get("authors", []):
                        if isinstance(a, dict):
                            name = (a.get("name", "") or "").strip()
                            if name:
                                authors.append(name)
                        elif isinstance(a, str):
                            name = a.strip()
                            if name:
                                authors.append(name)
                    entry["authors"] = authors if authors else None
                elif e.get("author"):
                    # Auteur unique
                    author = (e.get("author", "") or "").strip()
                    if author:
                        entry["authors"] = [author]
            except Exception as author_error:
                print(f"[discovery] Error processing authors: {author_error}")
                entry["authors"] = None
            
            # Filtrage des entrées vides
            if entry["title"] or entry["link"]:
                yield entry
            
    except Exception as e:
        print(f"[discovery] Error parsing feed content: {e}")
        # Retourne une liste vide en cas d'erreur
        return []