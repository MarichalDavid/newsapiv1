# app/services/nlp_entities.py - Version allégée sans spaCy/PyTorch
import re
from typing import Dict, List
from functools import lru_cache

# Import du service de mots-clés amélioré
try:
    from .nlp_keywords import extract_keywords
    YAKE_AVAILABLE = True
except ImportError:
    YAKE_AVAILABLE = False
    print("⚠️ YAKE not available for keyword extraction")

# 🔧 CORRECTION: Extraction d'entités légère basée sur des patterns
class LightweightNER:
    """Extracteur d'entités nommées léger basé sur des règles et patterns"""
    
    def __init__(self):
        # Patterns pour identifier des entités
        self.patterns = {
            'PERSON': [
                r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',  # Prénom Nom
                r'\b(?:M\.|Mr\.|Mme|Mrs\.|Dr\.) [A-Z][a-z]+\b',  # Titre + Nom
            ],
            'ORG': [
                r'\b[A-Z][a-z]*(?:\s+[A-Z][a-z]*)*\s+(?:Inc|Corp|Ltd|LLC|SA|SARL|SAS)\b',
                r'\b(?:Google|Microsoft|Apple|Amazon|Facebook|Meta|Twitter|Tesla|OpenAI|Anthropic)\b',
                r'\b[A-Z]{2,}(?:\s+[A-Z]{2,})*\b',  # Acronymes
            ],
            'LOCATION': [
                r'\b(?:Paris|London|New York|Berlin|Tokyo|Beijing|Moscow|Rome|Madrid)\b',
                r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:City|State|Province|Country)\b',
            ],
            'MONEY': [
                r'\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|billion|trillion))?',
                r'€[\d,]+(?:\.\d{2})?(?:\s*(?:millions?|milliards?))?',
                r'\b\d+(?:\.\d+)?\s*(?:dollars?|euros?|pounds?)\b',
            ],
            'DATE': [
                r'\b\d{1,2}/\d{1,2}/\d{4}\b',  # DD/MM/YYYY
                r'\b\d{4}-\d{2}-\d{2}\b',      # YYYY-MM-DD
                r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
            ]
        }
        
        # Listes d'entités communes (pré-compilées)
        self.known_entities = {
            'PERSON': [
                'Emmanuel Macron', 'Joe Biden', 'Vladimir Putin', 'Xi Jinping',
                'Elon Musk', 'Jeff Bezos', 'Bill Gates', 'Mark Zuckerberg'
            ],
            'ORG': [
                'Google', 'Microsoft', 'Apple', 'Amazon', 'Facebook', 'Meta',
                'Tesla', 'OpenAI', 'Anthropic', 'Netflix', 'Spotify', 'Uber',
                'UNESCO', 'WHO', 'NASA', 'FIFA', 'UEFA'
            ],
            'LOCATION': [
                'Paris', 'London', 'New York', 'Berlin', 'Tokyo', 'Beijing',
                'France', 'United States', 'Germany', 'Japan', 'China', 'Russia',
                'Europe', 'Asia', 'America', 'Africa'
            ]
        }
        
        # Compiler les patterns pour performance
        self.compiled_patterns = {}
        for entity_type, patterns in self.patterns.items():
            self.compiled_patterns[entity_type] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]

    def extract_entities_from_text(self, text: str) -> Dict[str, List[str]]:
        """Extrait les entités nommées du texte"""
        entities = {}
        
        if not text:
            return entities
        
        # 1. Recherche par patterns
        for entity_type, compiled_patterns in self.compiled_patterns.items():
            found = set()
            
            for pattern in compiled_patterns:
                matches = pattern.findall(text)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]  # Si le pattern a des groupes
                    match = match.strip()
                    if len(match) > 2:  # Filtrer les matches trop courts
                        found.add(match)
            
            if found:
                entities[entity_type] = list(found)
        
        # 2. Recherche dans les entités connues
        text_lower = text.lower()
        for entity_type, known_list in self.known_entities.items():
            found = set()
            
            for entity in known_list:
                if entity.lower() in text_lower:
                    found.add(entity)
            
            if found:
                if entity_type in entities:
                    entities[entity_type].extend(found)
                else:
                    entities[entity_type] = list(found)
        
        # 3. Déduplication et limitation
        for entity_type in entities:
            entities[entity_type] = list(set(entities[entity_type]))[:10]  # Max 10 par type
        
        return entities

# Instance globale
_lightweight_ner = LightweightNER()

@lru_cache(maxsize=2)
def _get_ner_instance(lang: str):
    """Retourne l'instance NER (cache pour compatibilité)"""
    return _lightweight_ner

def extract_entities(text: str, lang: str = "en") -> Dict[str, List[str]]:
    """
    Interface compatible avec l'ancienne version spaCy.
    Extrait les entités nommées du texte de manière légère.
    """
    if not text:
        return {}
    
    try:
        ner_instance = _get_ner_instance(lang or "en")
        return ner_instance.extract_entities_from_text(text)
    except Exception as e:
        print(f"[nlp_entities] Error extracting entities: {e}")
        return {}

def extract_enhanced_keywords(text: str, lang: str = "en", topk: int = 12) -> List[str]:
    """
    Extraction de mots-clés améliorée avec YAKE si disponible, 
    sinon fallback sur extraction basique.
    """
    if not text:
        return []
    
    if YAKE_AVAILABLE:
        try:
            return extract_keywords(text, lang, topk)
        except Exception as e:
            print(f"[nlp_entities] YAKE extraction failed: {e}")
    
    # Fallback: extraction basique par fréquence
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    word_freq = {}
    for word in words:
        if word not in ['this', 'that', 'with', 'have', 'will', 'from', 'they', 'been', 'said', 'each', 'which', 'their', 'time', 'were', 'more', 'about', 'after', 'first', 'would', 'there', 'could', 'other']:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Retourne les mots les plus fréquents
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, _ in sorted_words[:topk]]

# 🔧 FONCTION BONUS: Extraction d'entités spécifiques pour l'actualité
def extract_news_entities(text: str) -> Dict[str, List[str]]:
    """Extracteur spécialisé pour les entités d'actualité"""
    if not text:
        return {}
    
    news_patterns = {
        'COMPANY': [
            r'\b[A-Z][a-z]*(?:\s+[A-Z][a-z]*)*\s+(?:Inc|Corp|Ltd|LLC|SA|SARL|SAS|Group|Holdings)\b',
            r'\b(?:Google|Microsoft|Apple|Amazon|Facebook|Meta|Twitter|Tesla|OpenAI|Anthropic|Netflix|Spotify|Uber|Airbnb)\b',
        ],
        'POLITICAL_FIGURE': [
            r'\b(?:President|Prime Minister|Chancellor|Minister|Senator|Governor)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b',
            r'\b(?:Emmanuel Macron|Joe Biden|Vladimir Putin|Xi Jinping|Angela Merkel|Boris Johnson)\b',
        ],
        'CURRENCY': [
            r'\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|billion|trillion))?',
            r'€[\d,]+(?:\.\d{2})?(?:\s*(?:millions?|milliards?))?',
            r'\b\d+(?:\.\d+)?\s*(?:bitcoin|BTC|ETH|crypto)\b',
        ]
    }
    
    entities = {}
    
    for entity_type, patterns in news_patterns.items():
        found = set()
        
        for pattern in patterns:
            compiled_pattern = re.compile(pattern, re.IGNORECASE)
            matches = compiled_pattern.findall(text)
            
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                match = match.strip()
                if len(match) > 2:
                    found.add(match)
        
        if found:
            entities[entity_type] = list(found)[:5]  # Max 5 par type
    
    return entities