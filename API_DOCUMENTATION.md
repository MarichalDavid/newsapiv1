# Documentation API NewsIA

Une API complète pour la collecte, l'analyse et l'intelligence d'actualités avec IA.

## Table des matières

1. [Informations générales](#informations-générales)
2. [Authentification](#authentification)
3. [Endpoints par domaine fonctionnel](#endpoints-par-domaine-fonctionnel)
   - [Health & Monitoring](#health--monitoring)
   - [Articles](#articles)
   - [Sources](#sources)
   - [Topics](#topics)
   - [Clusters](#clusters)
   - [Recherche](#recherche)
   - [Sentiment](#sentiment)
   - [Résumés & Synthèses](#résumés--synthèses)
   - [Statistiques](#statistiques)
   - [Export](#export)
   - [Relations & Graphiques](#relations--graphiques)
   - [Administration](#administration)

## Informations générales

**Base URL**: `/api/v1` (sauf routes health et root)  
**Format de réponse**: JSON  
**Encodage**: UTF-8  
**CORS**: Activé pour tous les domaines  

### Codes de statut HTTP

- `200` - Succès
- `404` - Ressource non trouvée
- `422` - Erreur de validation des paramètres
- `500` - Erreur interne du serveur

## Authentification

Aucune authentification requise pour cette API.

---

## Endpoints par domaine fonctionnel

### Health & Monitoring

#### GET `/health`
**Description**: Health check basique de l'API.

**Réponse**:
```json
{
  "status": "ok",
  "message": "API NewsAI is running", 
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### GET `/health/detailed`
**Description**: Health check détaillé avec informations de base de données.

**Réponse**:
```json
{
  "status": "ok",
  "database": "connected",
  "articles_count": 1250,
  "active_sources": 45,
  "recent_articles_24h": 234,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### GET `/api/v1/system/status`
**Description**: Statut système complet incluant collection et cache.

**Réponse**:
```json
{
  "api": {"status": "healthy"},
  "collection": {
    "last_run": "2024-01-15T09:00:00Z",
    "status": "success"
  },
  "cache": {"available": true},
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### Articles

#### GET `/api/v1/articles`
**Description**: Liste des articles avec filtrage avancé.

**Paramètres de requête**:
- `limit` (int, 1-1000): Nombre d'articles (défaut: 20)
- `offset` (int, ≥0): Décalage pour pagination (défaut: 0)
- `q` (string): Recherche textuelle dans titre/contenu
- `topic` (array[string]): Filtrer par topics
- `region` (array[string]): Filtrer par région
- `keywords` (array[string]): Filtrer par mots-clés
- `lang` (array[string]): Filtrer par langue (ex: ["fr", "en"])
- `source_id` (array[int]): Filtrer par ID de source
- `domain` (array[string]): Filtrer par domaine
- `date_from` (datetime): Date de début
- `date_to` (datetime): Date de fin
- `has_full_text` (boolean): Articles avec texte complet uniquement
- `summary_source` (string): Type de résumé ("feed", "llm", "html")
- `order_by` (string): Champ de tri (défaut: "published_at")
- `order` (string): Ordre ("asc" ou "desc", défaut: "desc")

**Exemple d'URL**:
```
/api/v1/articles?limit=10&lang=fr&topic=technologie&date_from=2024-01-01T00:00:00Z
```

**Réponse**:
```json
[
  {
    "id": 1234,
    "source_id": 5,
    "url": "https://example.com/article",
    "canonical_url": "https://example.com/article",
    "domain": "example.com",
    "title": "Titre de l'article",
    "summary_feed": "Résumé RSS",
    "published_at": "2024-01-15T08:30:00Z",
    "authors": ["John Doe"],
    "full_text": "Texte complet...",
    "lang": "fr",
    "summary_final": "Résumé final",
    "fetched_at": "2024-01-15T09:00:00Z"
  }
]
```

#### GET `/api/v1/articles/{id}`
**Description**: Détails d'un article spécifique.

**Paramètres**:
- `id` (int, path): ID de l'article

**Réponse**: ArticleDetail avec champs supplémentaires (`entities`, `jsonld`, `raw`)

#### GET `/api/v1/articles/search`
**Description**: Recherche d'articles avec filtrage dans le contexte articles.

**Paramètres de requête**:
- `q` (string, requis): Requête de recherche
- `limit` (int, 1-100): Nombre de résultats (défaut: 20)
- `offset` (int, ≥0): Décalage (défaut: 0)
- `lang` (string): Langue
- `domain` (string): Domaine
- `topic` (string): Topic

**Réponse**:
```json
{
  "query": "intelligence artificielle",
  "filters": {
    "lang": "fr",
    "domain": null,
    "topic": "tech"
  },
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total_returned": 15
  },
  "articles": [...]
}
```

---

### Sources

#### GET `/api/v1/sources`
**Description**: Liste toutes les sources configurées.

**Réponse**:
```json
[
  {
    "id": 1,
    "name": "Le Monde",
    "feed_url": "https://www.lemonde.fr/rss/",
    "site_domain": "lemonde.fr",
    "method": "rss",
    "enrichment": "html",
    "frequency_minutes": 10,
    "active": true
  }
]
```

#### POST `/api/v1/sources/refresh`
**Description**: Recharge les sources depuis le fichier de configuration sans supprimer les articles existants.

**Réponse**:
```json
{
  "status": "ok",
  "count": 45,
  "message": "Sources rechargées sans affecter les articles"
}
```

#### GET `/api/v1/sources/{source_id}`
**Description**: Détails d'une source spécifique avec statistiques.

**Paramètres**:
- `source_id` (int, path): ID de la source

**Réponse**:
```json
{
  "id": 1,
  "name": "Le Monde",
  "feed_url": "https://www.lemonde.fr/rss/",
  "site_domain": "lemonde.fr",
  "active": true,
  "article_count": 1247,
  "last_article_date": "2024-01-15T08:30:00Z"
}
```

---

### Topics

#### GET `/api/v1/topics`
**Description**: Liste des topics extraits des articles avec fallback sur keywords.

**Réponse**:
```json
[
  {
    "topic": "intelligence artificielle",
    "count": 145
  },
  {
    "topic": "politique",
    "count": 98
  }
]
```

#### GET `/api/v1/topics/{topic}/articles`
**Description**: Articles associés à un topic spécifique.

**Paramètres**:
- `topic` (string, path): Nom du topic
- `limit` (int): Nombre d'articles (défaut: 50)
- `offset` (int): Décalage (défaut: 0)

**Réponse**:
```json
[
  {
    "id": 1234,
    "title": "Avancées en IA",
    "url": "https://example.com/article",
    "canonical_url": "https://example.com/article",
    "domain": "example.com",
    "published_at": "2024-01-15T08:30:00Z",
    "lang": "fr",
    "keywords": ["ia", "technologie"],
    "topics": ["intelligence artificielle"],
    "summary_final": "Résumé...",
    "summary_source": "llm"
  }
]
```

#### GET `/api/v1/topics/{topic_name}`
**Description**: Détails d'un topic avec statistiques et articles récents.

**Réponse**:
```json
{
  "topic": "intelligence artificielle",
  "article_count": 145,
  "recent_articles": [
    {
      "id": 1234,
      "title": "Avancées en IA",
      "canonical_url": "https://example.com/article",
      "domain": "example.com",
      "published_at": "2024-01-15T08:30:00Z"
    }
  ]
}
```

---

### Clusters

#### GET `/api/v1/clusters`
**Description**: Liste des clusters d'articles récents.

**Paramètres de requête**:
- `since_hours` (int, 1-168): Période en heures (défaut: 48)
- `limit_clusters` (int, 1-1000): Nombre maximum de clusters (défaut: 100)

**Réponse**:
```json
[
  {
    "cluster_id": "tech_ai_2024_15",
    "n": 15,
    "last_pub": "2024-01-15T08:30:00Z"
  }
]
```

#### GET `/api/v1/clusters/{cluster_id}/articles`
**Description**: Articles d'un cluster spécifique.

**Paramètres**:
- `cluster_id` (string, path): ID du cluster
- `limit` (int, 1-1000): Nombre d'articles (défaut: 50)
- `offset` (int, ≥0): Décalage (défaut: 0)

#### GET `/api/v1/clusters/{cluster_id}`
**Description**: Détails d'un cluster avec métadonnées.

**Réponse**:
```json
{
  "cluster_id": "tech_ai_2024_15",
  "article_count": 15,
  "first_article": "2024-01-14T20:30:00Z",
  "last_article": "2024-01-15T08:30:00Z",
  "domains": ["lemonde.fr", "figaro.fr", "bbc.com"]
}
```

---

### Recherche

#### GET `/api/v1/search/semantic`
**Description**: Recherche sémantique dans les articles.

**Paramètres de requête**:
- `q` (string, requis): Requête de recherche
- `k` (int, ≤200): Nombre de résultats (défaut: 10)

**Réponse**:
```json
[
  {
    "id": 1234,
    "title": "Titre de l'article",
    "summary": "Résumé...",
    "domain": "example.com",
    "published_at": "2024-01-15T08:30:00Z",
    "canonical_url": "https://example.com/article",
    "url": "https://example.com/article"
  }
]
```

#### GET `/api/v1/search`
**Description**: Recherche globale d'articles.

**Paramètres de requête**:
- `q` (string, requis): Requête de recherche
- `limit` (int, 1-100): Nombre de résultats (défaut: 20)
- `lang` (string): Langue

#### GET `/api/v1/search/entities`
**Description**: Recherche d'articles par entités nommées.

**Paramètres de requête**:
- `entity_type` (string, requis): Type d'entité (PERSON, ORG, LOCATION, etc.)
- `entity_name` (string): Nom de l'entité à rechercher
- `limit` (int, 1-200): Nombre d'articles (défaut: 50)
- `since_days` (int, 1-365): Période en jours (défaut: 30)

**Réponse**:
```json
{
  "query": {
    "entity_type": "PERSON",
    "entity_name": "Emmanuel Macron",
    "since_days": 30,
    "limit": 50
  },
  "articles": [...],
  "entity_mentions": {
    "Emmanuel Macron": {
      "count": 23,
      "articles": [1234, 1235, 1236]
    }
  },
  "total_articles": 15
}
```

#### GET `/api/v1/search/similar/{article_id}`
**Description**: Trouve des articles similaires basés sur les mots-clés et topics.

**Paramètres**:
- `article_id` (int, path, ≥1): ID de l'article de référence
- `limit` (int, 1-50): Nombre d'articles similaires (défaut: 10)

**Réponse**:
```json
{
  "reference_article": {
    "id": 1234,
    "title": "Article de référence",
    "url": "https://example.com/article",
    "domain": "example.com",
    "keywords": ["tech", "ai"],
    "topics": ["intelligence artificielle"]
  },
  "similar_articles": [...],
  "total_found": 8,
  "method": "text_and_metadata_similarity"
}
```

---

### Sentiment

#### GET `/api/v1/sentiment/global`
**Description**: Analyse du sentiment global de tous les articles.

**Paramètres de requête**:
- `days` (int, 1-90): Période en jours (défaut: 7)
- `granularity` (string): "daily" ou "weekly" (défaut: "daily")

**Réponse**:
```json
{
  "global_sentiment": {
    "period_days": 7,
    "granularity": "daily",
    "total_articles": 1500,
    "overall_sentiment_score": 0.125,
    "sentiment_distribution": {
      "positive": 650,
      "neutral": 600,
      "negative": 250,
      "positive_pct": 43.3,
      "neutral_pct": 40.0,
      "negative_pct": 16.7
    }
  },
  "daily_breakdown": [
    {
      "period": "2024-01-15",
      "total_articles": 234,
      "avg_sentiment": 0.15,
      "positive_count": 98,
      "neutral_count": 95,
      "negative_count": 41
    }
  ]
}
```

#### GET `/api/v1/sentiment/topics`
**Description**: Liste des topics avec données de sentiment.

**Réponse**:
```json
[
  {
    "topic": "économie",
    "article_count": 234,
    "avg_sentiment": -0.05,
    "positive_count": 89,
    "neutral_count": 98,
    "negative_count": 47
  }
]
```

#### GET `/api/v1/sentiment/topic/{topic_identifier}`
**Description**: Analyse du sentiment pour un topic spécifique.

**Paramètres**:
- `topic_identifier` (string, path): Nom du topic ou index numérique (base 1)
- `days` (int, 1-90): Période en jours (défaut: 7)

#### GET `/api/v1/sentiment/source/{domain}`
**Description**: Analyse du sentiment pour une source spécifique.

**Paramètres**:
- `domain` (string, path): Domaine de la source
- `days` (int, 1-90): Période en jours (défaut: 7)

---

### Résumés & Synthèses

#### GET `/api/v1/summaries`
**Description**: Liste ou régénère les résumés d'articles.

**Paramètres de requête**:
- `since_hours` (int, 1-336): Période en heures (défaut: 24)
- `limit` (int, 1-50): Nombre d'articles (défaut: 10)
- `offset` (int, ≥0): Décalage (défaut: 0)
- `lang` (string): Langue de sortie ("fr" ou "en")
- `regen` (boolean): Régénérer les résumés via LLM (défaut: false)
- `persist` (boolean): Sauvegarder les résumés générés (défaut: false)

**Réponse**:
```json
[
  {
    "id": 1234,
    "source_id": 5,
    "canonical_url": "https://example.com/article",
    "domain": "example.com",
    "title": "Titre de l'article",
    "published_at": "2024-01-15T08:30:00Z",
    "lang": "fr",
    "summary_final": "Résumé final de l'article...",
    "summary_source": "llm",
    "url": "https://example.com/article"
  }
]
```

#### GET `/api/v1/summaries/general`
**Description**: Synthèse générale de l'actualité.

**Paramètres de requête**:
- `since_hours` (int, 1-168): Période en heures (défaut: 24)
- `target_sentences` (int, 5-50): Nombre de phrases cibles (défaut: 10)
- `lang` (string): Langue de sortie (défaut: "fr")

**Réponse**:
```json
{
  "synthesis": "Synthèse générale de l'actualité des dernières 24h...",
  "period_hours": 24,
  "articles_analyzed": 20,
  "language": "fr",
  "generated_at": "2024-01-15T10:30:00Z"
}
```

#### GET `/api/v1/summaries/topic/{topic_name}`
**Description**: Synthèse pour un topic spécifique.

**Paramètres**:
- `topic_name` (string, path): Nom du topic
- `since_hours` (int, 1-168): Période en heures (défaut: 48)
- `target_sentences` (int, 3-30): Nombre de phrases cibles (défaut: 8)
- `lang` (string): Langue de sortie (défaut: "fr")

#### GET `/api/v1/summaries/source/{domain}`
**Description**: Synthèse pour une source spécifique.

#### GET `/api/v1/summaries/trending`
**Description**: Synthèse des topics en tendance.

**Paramètres de requête**:
- `since_hours` (int, 1-168): Période en heures (défaut: 24)
- `min_articles` (int, 2-50): Minimum d'articles par topic (défaut: 3)
- `limit_topics` (int, 5-20): Nombre maximum de topics (défaut: 10)
- `lang` (string): Langue (défaut: "fr")

**Réponse**:
```json
{
  "trending_topics": [
    {
      "topic": "intelligence artificielle",
      "article_count": 23,
      "trend_score": 0.96
    }
  ],
  "period_hours": 24,
  "total_trending_topics": 8,
  "language": "fr",
  "generated_at": "2024-01-15T10:30:00Z"
}
```

#### GET `/api/v1/synthesis`
**Description**: Synthèse personnalisée avec filtrage avancé.

**Paramètres de requête**:
- `q` (string): Mot-clé de recherche
- `source_id` (int, ≥1): ID de source
- `topic` (string): Topic spécifique
- `since_hours` (int, 1-720): Période en heures (défaut: 24)
- `limit_docs` (int, 5-120): Nombre de documents analysés (défaut: 30)
- `lang` (string): Langue de sortie (défaut: "fr")

**Réponse**:
```json
{
  "filters": {
    "q": "intelligence artificielle",
    "source_id": null,
    "topic": "tech",
    "since_hours": 24,
    "limit_docs": 30,
    "lang": "fr"
  },
  "docs_count": 15,
  "synthesis": "Synthèse basée sur les filtres appliqués...",
  "sample_articles": [
    {
      "title": "Avancées en IA",
      "url": "https://example.com/article",
      "published_at": "2024-01-15T08:30:00Z"
    }
  ]
}
```

---

### Statistiques

#### GET `/api/v1/stats/general`
**Description**: Statistiques générales de l'API.

**Réponse**:
```json
{
  "total_articles": 12450,
  "unique_domains": 87,
  "total_clusters": 156,
  "articles_24h": 234
}
```

#### GET `/api/v1/stats/sources`
**Description**: Statistiques par source.

**Réponse**:
```json
[
  {
    "name": "Le Monde",
    "site_domain": "lemonde.fr",
    "article_count": 1247,
    "last_article": "2024-01-15T08:30:00Z"
  }
]
```

#### GET `/api/v1/stats/topics`
**Description**: Statistiques par topic.

**Réponse**:
```json
[
  {
    "topic": "politique",
    "article_count": 456,
    "recent_count": 34
  }
]
```

#### GET `/api/v1/stats/timeline`
**Description**: Timeline des statistiques.

**Paramètres de requête**:
- `days` (int, 1-90): Période en jours (défaut: 30)

**Réponse**:
```json
[
  {
    "date": "2024-01-15",
    "article_count": 234,
    "source_count": 45
  }
]
```

---

### Export

#### GET `/api/v1/exports/articles.csv`
**Description**: Export CSV des articles avec tous les filtres disponibles.

**Paramètres**: Mêmes filtres que `/api/v1/articles`

**Réponse**: Fichier CSV avec colonnes :
```
id,title,domain,canonical_url,published_at,lang,summary_source,keywords,topics
```

#### GET `/api/v1/exports/sentiment.csv`
**Description**: Export CSV des données de sentiment.

**Paramètres de requête**:
- `days` (int, 1-90): Période en jours (défaut: 7)

**Réponse**: Fichier CSV avec colonnes :
```
date,domain,total_articles,positive,neutral,negative,avg_sentiment
```

#### GET `/api/v1/exports/topics.json`
**Description**: Export JSON des topics.

#### GET `/api/v1/exports/stats.json`
**Description**: Export JSON des statistiques générales.

---

### Relations & Graphiques

#### GET `/api/v1/graph/cluster/{cluster_id}`
**Description**: Génère un graphique pour un cluster spécifique.

**Paramètres**:
- `cluster_id` (string, path): ID du cluster

**Réponse**:
```json
{
  "nodes": [
    {"id": "a1234", "label": "Titre article", "type": "article"},
    {"id": "lemonde.fr", "label": "lemonde.fr", "type": "source"}
  ],
  "edges": [
    {"source": "a1234", "target": "lemonde.fr", "type": "covers"}
  ]
}
```

#### GET `/api/v1/relations/sources`
**Description**: Relations entre sources d'actualités.

**Paramètres de requête**:
- `date` (string, requis): Date au format YYYY-MM-DD
- `relation` (string): Type de relation ("co_coverage", "temporal_correlation", "topic_similarity", défaut: "co_coverage")
- `min_weight` (float, ≥0): Poids minimum (défaut: 1.0)
- `limit` (int, 1-200): Nombre de relations (défaut: 10)

#### GET `/api/v1/relations/network`
**Description**: Statistiques du réseau de sources.

**Paramètres de requête**:
- `date` (string, requis): Date au format YYYY-MM-DD

#### GET `/api/v1/relations/sources/{domain}`
**Description**: Relations pour une source spécifique.

**Paramètres**:
- `domain` (string, path): Domaine de la source
- `date` (string, requis): Date au format YYYY-MM-DD
- `relation` (string): Type de relation (défaut: "co_coverage")
- `min_weight` (float, ≥0): Poids minimum (défaut: 1.0)
- `limit` (int, 1-100): Nombre de relations (défaut: 20)

---

### Administration

#### GET `/`
**Description**: Point d'entrée racine de l'API.

**Réponse**:
```json
{
  "message": "NewsAI API",
  "version": "1.0.0",
  "status": "operational",
  "docs": "/docs",
  "health": "/health"
}
```

#### GET `/api/v1/admin/diagnose`
**Description**: Diagnostic complet du système.

**Réponse**:
```json
{
  "status": "success",
  "timestamp": "2024-01-15T10:30:00Z",
  "sources": {
    "total": 50,
    "active": 45,
    "inactive": 5
  },
  "articles": {
    "total": 12450,
    "last_24h": 234,
    "last_fetch": "2024-01-15T09:00:00Z"
  },
  "active_sources_sample": [...],
  "config_file_exists": true,
  "recommendations": [
    "✅ Tout semble OK",
    "✅ Articles récents", 
    "✅ Config trouvée"
  ]
}
```

#### POST `/api/v1/admin/fix-sources`
**Description**: Répare les sources à partir du fichier de configuration.

#### POST `/api/v1/admin/collect`
**Description**: Déclenche une collecte manuelle d'articles.

**Réponse**:
```json
{
  "status": "success",
  "message": "Collecte manuelle terminée",
  "result": {
    "articles_collected": 23,
    "sources_processed": 45,
    "duration_seconds": 125
  },
  "cache_cleared": true,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### GET `/api/v1/admin/collection-status`
**Description**: Statut de la collecte automatique.

#### POST `/api/v1/admin/process-topics`
**Description**: Traite les articles pour extraire les topics et assigner les clusters.

**Paramètres de requête**:
- `limit` (int): Nombre d'articles à traiter (défaut: 50)
- `since_hours` (int): Période en heures (défaut: 24)
- `fallback` (boolean): Utiliser méthode de fallback (défaut: true)

#### POST `/api/v1/admin/process-sentiment`
**Description**: Traite les articles pour analyser le sentiment.

**Paramètres de requête**:
- `limit` (int): Nombre d'articles à traiter (défaut: 50)
- `since_hours` (int): Période en heures (défaut: 24)
- `use_llm` (boolean): Utiliser LLM pour analyse (défaut: true)
- `fallback` (boolean): Utiliser méthode de fallback (défaut: true)

---

## Exemples d'utilisation

### Récupérer les derniers articles en français
```bash
curl "http://localhost:8000/api/v1/articles?lang=fr&limit=10&order_by=published_at&order=desc"
```

### Rechercher des articles sur l'IA
```bash
curl "http://localhost:8000/api/v1/search?q=intelligence+artificielle&limit=20"
```

### Obtenir une synthèse générale des dernières 48h
```bash
curl "http://localhost:8000/api/v1/summaries/general?since_hours=48&lang=fr"
```

### Analyser le sentiment sur 7 jours
```bash
curl "http://localhost:8000/api/v1/sentiment/global?days=7&granularity=daily"
```

### Exporter des articles en CSV
```bash
curl "http://localhost:8000/api/v1/exports/articles.csv?lang=fr&date_from=2024-01-01" > articles.csv
```

---

## Notes techniques

### Performance
- Limitation des appels LLM pour éviter les timeouts
- Cache Redis disponible pour optimiser les réponses
- Pagination recommandée pour les grandes collections

### Formats de date
- Toutes les dates sont en format ISO 8601 UTC
- Les paramètres de date acceptent format `YYYY-MM-DDTHH:MM:SSZ`

### Gestion d'erreurs
- Validation automatique des paramètres avec Pydantic
- Messages d'erreur détaillés en français
- Fallbacks automatiques pour assurer la disponibilité

Cette documentation couvre l'ensemble des endpoints disponibles dans l'API NewsIA avec leurs paramètres, formats de réponse et exemples d'utilisation.