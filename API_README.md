# API de veille & analyse d'articles — Documentation des Endpoints

> **Version** : 1.0.0  
> **Base URL** : `https://api.example.com` (remplacez par votre domaine)  
> **Formats** : JSON (UTF‑8)  
> **Auth** : (optionnelle) `Authorization: Bearer <token>`

---

## Conventions générales

- **Dates** : ISO‑8601 (`YYYY-MM-DDTHH:MM:SSZ`). Les paramètres `from_date` et `to_date` sont inclusifs.
- **Pagination** : `limit` (défaut 20, max recommandé 100), `offset` (défaut 0).
- **Filtres communs** : la plupart des endpoints supportent `from_date` et `to_date`.
- **Erreurs** : réponses d’erreur au format :
  ```json
  { "error": { "code": "string", "message": "string", "details": {} } }
  ```

---

## Articles

### GET `/articles`
**Description** : Récupère une liste d'articles.

**Paramètres de requête** :
- `limit` *(int, optionnel)* — nombre max d’articles (défaut : 20)  
- `offset` *(int, optionnel)* — décalage pour la pagination (défaut : 0)  
- `source_id` *(string, optionnel)* — filtre par source  
- `from_date` *(datetime, optionnel)* — publiés après cette date  
- `to_date` *(datetime, optionnel)* — publiés avant cette date  

**Réponse 200** : liste d’articles
```json
{
  "items": [
    {
      "id": "art_123",
      "title": "Titre",
      "summary": "Résumé…",
      "url": "https://…",
      "published_at": "2025-08-15T12:34:56Z",
      "source_id": "src_001",
      "language": "fr",
      "keywords": ["économie", "ia"],
      "region": "EU",
      "author": "Nom Auteur"
    }
  ],
  "pagination": { "limit": 20, "offset": 0, "total": 345 }
}
```

---

### GET `/articles/{article_id}`
**Description** : Détails d’un article.

**Paramètres de chemin** :
- `article_id` *(string)* — identifiant de l’article

**Réponse 200** :
```json
{
  "id": "art_123",
  "title": "Titre",
  "content": "Texte complet…",
  "summary": "Résumé…",
  "url": "https://…",
  "published_at": "2025-08-15T12:34:56Z",
  "source_id": "src_001",
  "language": "fr",
  "keywords": ["économie", "ia"],
  "region": "EU",
  "author": "Nom Auteur",
  "cluster_id": "clu_42"
}
```

---

## Clusters

### GET `/clusters`
**Description** : Liste de clusters d’articles (groupes d’articles similaires).

**Paramètres** :
- `limit` *(int, optionnel)* — défaut 20  
- `offset` *(int, optionnel)* — défaut 0  
- `from_date` *(datetime, optionnel)*  
- `to_date` *(datetime, optionnel)*

**Réponse 200** :
```json
{
  "items": [
    {
      "id": "clu_42",
      "label": "IA & industrie",
      "size": 7,
      "created_at": "2025-08-15T10:00:00Z",
      "centroid_keywords": ["IA", "robotique", "productivité"]
    }
  ],
  "pagination": { "limit": 20, "offset": 0, "total": 73 }
}
```

---

### GET `/clusters/{cluster_id}`
**Description** : Détails d’un cluster.

**Paramètres** :
- `cluster_id` *(string)*

**Réponse 200** :
```json
{
  "id": "clu_42",
  "label": "IA & industrie",
  "created_at": "2025-08-15T10:00:00Z",
  "articles": ["art_123", "art_456"],
  "centroid_keywords": ["IA", "robotique", "productivité"]
}
```

---

## Recherche

### GET `/search`
**Description** : Recherche d’articles.

**Paramètres** :
- `q` *(string, requis)* — terme de recherche  
- `limit` *(int, optionnel)* — défaut 20  
- `offset` *(int, optionnel)* — défaut 0  
- `from_date` *(datetime, optionnel)*  
- `to_date` *(datetime, optionnel)*

**Réponse 200** :
```json
{
  "items": [
    {
      "id": "art_123",
      "title": "…",
      "snippet": "Extrait qui matche la requête…",
      "score": 12.34
    }
  ],
  "pagination": { "limit": 20, "offset": 0, "total": 128 }
}
```

---

## Sentiment

### GET `/sentiment/articles/{article_id}`
**Description** : Analyse de sentiment pour un article.

**Paramètres** :
- `article_id` *(string)*

**Réponse 200** :
```json
{
  "article_id": "art_123",
  "sentiment": { "label": "positif", "score": 0.83 },
  "emotion": { "joy": 0.42, "anger": 0.05, "fear": 0.10, "sadness": 0.08 }
}
```

### GET `/sentiment/stats`
**Description** : Statistiques globales de sentiment.

**Paramètres** :
- `from_date` *(datetime, optionnel)*  
- `to_date` *(datetime, optionnel)*

**Réponse 200** :
```json
{
  "count": 1000,
  "distribution": { "positif": 0.51, "neutre": 0.31, "negatif": 0.18 },
  "avg_score": 0.42
}
```

---

## Sources

### GET `/sources`
**Description** : Liste des sources.

**Paramètres** :
- `limit` *(int, optionnel)* — défaut 20  
- `offset` *(int, optionnel)* — défaut 0

**Réponse 200** :
```json
{
  "items": [
    {
      "id": "src_001",
      "name": "Nom de la source",
      "url": "https://…",
      "feed_url": "https://…/rss.xml",
      "language": "fr"
    }
  ],
  "pagination": { "limit": 20, "offset": 0, "total": 12 }
}
```

### POST `/sources`
**Description** : Ajoute une nouvelle source.

**Corps** :
```json
{
  "name": "Nom de la source",
  "url": "https://example.com",
  "feed_url": "https://example.com/rss.xml",
  "language": "fr"
}
```

**Réponse 201** :
```json
{
  "id": "src_123",
  "name": "Nom de la source",
  "url": "https://example.com",
  "feed_url": "https://example.com/rss.xml",
  "language": "fr",
  "created_at": "2025-08-15T11:22:33Z"
}
```

### GET `/sources/{source_id}`
**Description** : Détails d’une source.

**Paramètres** :
- `source_id` *(string)*

**Réponse 200** :
```json
{
  "id": "src_001",
  "name": "Nom de la source",
  "url": "https://…",
  "feed_url": "https://…/rss.xml",
  "language": "fr",
  "status": "active"
}
```

---

## Statistiques

### GET `/stats/overview`
**Description** : Aperçu des statistiques globales.

**Paramètres** :
- `from_date` *(datetime, optionnel)*  
- `to_date` *(datetime, optionnel)*

**Réponse 200** :
```json
{
  "articles_total": 12345,
  "sources_total": 120,
  "top_keywords": ["ia", "économie", "sécurité"],
  "articles_last_24h": 320
}
```

---

## Résumé

### GET `/summaries/{article_id}`
**Description** : Génère (ou retourne) le résumé pour un article.

**Paramètres** :
- `article_id` *(string)*

**Réponse 200** :
```json
{ "article_id": "art_123", "summary": "Résumé factuel et concis…" }
```

---

## Synthèse

### GET `/synthesis`
**Description** : Génère une synthèse sur un sujet.

**Paramètres** :
- `topic` *(string, requis)* — sujet/terme de synthèse  
- `from_date` *(datetime, optionnel)*  
- `to_date` *(datetime, optionnel)*

**Réponse 200** :
```json
{
  "topic": "IA industrielle",
  "summary": "Les 4–7 points clés…",
  "sources": [
    { "title": "Article A", "domain": "siteA.com", "url": "https://…" },
    { "title": "Article B", "domain": "siteB.com", "url": "https://…" }
  ]
}
```

---

## Relations

### GET `/relations/graph`
**Description** : Graphe des relations entre entités (personnes, organisations, pays…).

**Paramètres** :
- `from_date` *(datetime, optionnel)*  
- `to_date` *(datetime, optionnel)*

**Réponse 200** :
```json
{
  "nodes": [
    { "id": "org_openai", "type": "organization", "label": "OpenAI" },
    { "id": "cn_france", "type": "country", "label": "France" }
  ],
  "edges": [
    { "source": "org_openai", "target": "cn_france", "relation": "partnership" }
  ]
}
```

---

## Santé

### GET `/health`
**Description** : État de santé de l’API.

**Réponse 200** :
```json
{ "status": "ok", "version": "1.0.0" }
```

---

## Exports

### GET `/exports/articles`
**Description** : Exporte les articles.

**Paramètres** :
- `format` *(string, requis)* — `csv` ou `json`  
- `from_date` *(datetime, optionnel)*  
- `to_date` *(datetime, optionnel)*

**Réponses** :
- **200** : fichier téléchargeable (Content-Type `text/csv` ou `application/json`)
- **400** : format non supporté

---

## Codes HTTP usuels

- **200 OK** — Requête réussie  
- **201 Created** — Ressource créée  
- **400 Bad Request** — Paramètres invalides  
- **401 Unauthorized** — Authentification requise/invalide  
- **404 Not Found** — Ressource inexistante  
- **429 Too Many Requests** — Limite de débit atteinte  
- **500 Internal Server Error** — Erreur serveur

---

## Notes de mise en œuvre

- Pensez à limiter `limit` et à fournir `Link` headers pour faciliter la pagination (RFC 5988).
- Les dates sont normalisées en UTC côté API.
- Les champs facultatifs non disponibles peuvent être `null` ou omis selon vos conventions.
