from fastapi import FastAPI
from .core.db import get_session
from .core.models import Source
from .api.routes_sources import router as sources_router
from .api.routes_articles import router as articles_router
from .api.routes_summaries import router as summaries_router
from .api.routes_topics import router as topics_router
from .api.routes_clusters import router as clusters_router
from .api.routes_exports import router as exports_router
from fastapi.middleware.cors import CORSMiddleware
from .middleware_cache import RedisGetCacheMiddleware
from .api.routes_synthesis import router as synthesis_router
from .api.routes_search import router as search_router
from .api.routes_sentiment import router as sentiment_router
from .api.routes_graph import router as graph_router
from .api.routes_relations import router as relations_router
from .api.routes_health import router as health_router
from .api.routes_stats import router as stats_router

# ✅ NOUVEAU: Import de votre collecteur existant (garder votre version)
from .services.collector import run_collection_once
import asyncio
import os

app = FastAPI(title="NewsIA API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes existantes
app.include_router(sources_router, prefix="/api/v1")
app.include_router(articles_router, prefix="/api/v1")
app.include_router(summaries_router, prefix="/api/v1")
app.include_router(topics_router, prefix="/api/v1")
app.include_router(clusters_router, prefix="/api/v1")
app.include_router(exports_router, prefix="/api/v1")
app.include_router(synthesis_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(sentiment_router, prefix="/api/v1")
app.include_router(graph_router, prefix="/api/v1")
app.include_router(relations_router, prefix="/api/v1")
app.include_router(health_router)
app.include_router(stats_router, prefix="/api/v1")

# ✅ NOUVEAUX ENDPOINTS: Administration de la collecte (garder vos endpoints existants)
@app.post("/api/v1/admin/collect")
async def manual_collection():
    """Déclenche une collecte manuelle des articles"""
    try:
        async for db in get_session():
            print("🔄 Démarrage de la collecte manuelle...")
            await run_collection_once(db)
            print("✅ Collecte manuelle terminée")
            break  # On sort après la première session
        return {"status": "Collection manuelle terminée avec succès"}
    except Exception as e:
        print(f"❌ Erreur collecte manuelle: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/v1/admin/collection-status")
async def collection_status():
    """Statut de la collecte automatique"""
    
    # Vérifier si le worker tourne
    worker_enabled = os.getenv("ENABLE_AUTO_COLLECTION", "true").lower() == "true"
    collection_interval = int(os.getenv("COLLECTION_INTERVAL_MINUTES", "30"))
    
    # Stats de la dernière collecte
    try:
        async for db in get_session():
            from sqlalchemy import text
            # Compter les articles récents
            result = await db.execute(text("""
                SELECT 
                    COUNT(*) as total_articles,
                    COUNT(*) FILTER (WHERE fetched_at >= NOW() - INTERVAL '1 hour') as articles_last_hour,
                    COUNT(DISTINCT source_id) as active_sources,
                    MAX(fetched_at) as last_fetch_time
                FROM articles
            """))
            stats = result.mappings().first()
            break
    except Exception as e:
        stats = {"total_articles": 0, "articles_last_hour": 0, "active_sources": 0, "last_fetch_time": None}
    
    return {
        "collection_enabled": worker_enabled,
        "interval_minutes": collection_interval,
        "worker_running": "Vérifiez le service 'worker' dans Docker",
        "last_fetch_time": stats["last_fetch_time"],
        "total_articles": stats["total_articles"],
        "articles_last_hour": stats["articles_last_hour"],
        "active_sources": stats["active_sources"]
    }

@app.get("/health")
def health():
    return {"status":"ok"}

from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
from sqlalchemy import text
import os, json

REQS = Counter("newsia_requests_total", "Total API requests", ["path"])

@app.on_event("startup")
async def _bootstrap():
    # Import feeds from config if no sources
    try:
        async for db in get_session():
            res = await db.execute(text("SELECT COUNT(*) FROM sources"))
            n = res.scalar_one()
            if n == 0:
                path = os.getenv("FEEDS_FILE", "/app/config/rss_feeds_global.json")
                if os.path.exists(path):
                    data = json.load(open(path,"r",encoding="utf-8"))
                    from urllib.parse import urlparse
                    from sqlalchemy import insert
                    for it in data:
                        u = it.get("url"); name = it.get("name") or urlparse(u).netloc
                        dom = urlparse(u).netloc
                        await db.execute(insert(Source).values(name=name, feed_url=u, site_domain=dom, method="rss", enrichment="html", active=True))
                    await db.commit()
                    print(f"✅ {len(data)} sources RSS importées")
                else:
                    print("⚠️  Fichier de configuration RSS non trouvé")
            else:
                print(f"✅ {n} sources déjà configurées")
    except Exception as e:
        print("❌ Erreur bootstrap:", e, flush=True)

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)