# NewsIA API (v0.2) — FastAPI + Collector + Ollama

Projet prêt à l'emploi avec **docker-compose** : collecte RSS (+fallback sitemaps), enrichissement texte, déduplication (hash + **simhash**), NER **spaCy FR/EN**, keywords (YAKE), **cache LLM**, endpoints **/topics**, **/clusters**, **/exports**.

## Démarrage

```bash
cd newsapi
cp .env.example .env
docker compose up -d --build
```

### Télécharger les modèles spaCy (dans le conteneur API)
```bash
docker compose exec api python -m spacy download en_core_web_sm
docker compose exec api python -m spacy download fr_core_news_sm
```

### Charger les sources (depuis `config/rss_feeds_global.json`)
```bash
curl -X POST http://localhost:8000/api/v1/sources/refresh
```

### Lancer / vérifier
- Health: `GET http://localhost:8000/health`
- Articles: `GET http://localhost:8000/api/v1/articles?limit=20`
- Synthèse générale: `GET /api/v1/summaries/general?since_hours=24&target_sentences=12`

## Nouveautés
- **simhash + cluster_id** → `GET /api/v1/clusters`
- **Cache LLM** (synthèses par filtres)
- **Sitemap fallback** si feed vide/HS
- **spaCy NER FR/EN** (`nlp_entities.py`)
- Endpoints : `/api/v1/topics`, `/api/v1/clusters`, `/api/v1/exports/articles.csv`

## Exports CSV
```
GET /api/v1/exports/articles.csv?lang=fr&topic=tech&date_from=2025-08-01T00:00:00Z
```

## Remarques
- Pas d'images collectées.
- Thématiques simples (basées keywords) ; à remplacer par BERTopic plus tard.
- Le worker collecte en boucle (fréquence `.env`).

## collecte manuele
http://localhost:8000/api/v1/sources/refresh
$code = @"
import asyncio
from app.core.db import get_session
from app.services.collector import run_collection_once
async def main():
    async for s in get_session():
        await run_collection_once(s)
asyncio.run(main())
"@
$code | docker compose exec -T worker python -


docker compose exec worker bash -lc 'python - <<PY
from app.core.db import get_session
from app.services.collector import run_collection_once
import asyncio

async def main():
    async for s in get_session():
        await run_collection_once(s)

asyncio.run(main())
PY'

docker compose exec db psql -U news -d news -c "SELECT COUNT(*) FROM articles;"
