# app/main.py - Production-ready version corrigé
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import os
import json
from contextlib import asynccontextmanager
from datetime import datetime
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Conditional imports with fallbacks
try:
    from .services.enhanced_cache_service import EnhancedCacheService
    cache = EnhancedCacheService()
    CACHE_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    CACHE_AVAILABLE = False
    cache = None

# Import routes
from .api import (
    routes_articles,
    routes_sources, 
    routes_topics,
    routes_clusters,
    routes_stats,
    routes_search,
    routes_sentiment,
    routes_summaries,
    routes_synthesis,
    routes_exports,
    routes_health,
    routes_graph,
    routes_relations
)

# Import services
from .core.db import get_session
from .core.models import Source
from .services.collector import run_collection_once, get_collection_health

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("🚀 NewsAI API starting up...")
    
    if CACHE_AVAILABLE and cache:
        try:
            await cache.init()
            logger.info("✅ Cache service initialized")
        except Exception as e:
            logger.warning(f"⚠️ Cache initialization failed: {e}")
    
    # ✅ CORRECTION: Bootstrap sources automatiquement
    await bootstrap_sources()
    
    logger.info("✅ NewsAI API startup completed")
    
    yield
    
    # Shutdown
    logger.info("🔥 NewsAI API shutting down...")
    if CACHE_AVAILABLE and cache:
        logger.info("✅ Cache cleanup completed")
    logger.info("👋 NewsAI API shutdown completed")

async def bootstrap_sources():
    """Bootstrap les sources RSS depuis le fichier de config"""
    try:
        async for db in get_session():
            # Vérifier si on a déjà des sources
            result = await db.execute(text("SELECT COUNT(*) FROM sources WHERE active = true"))
            active_count = result.scalar()
            
            if active_count == 0:
                logger.info("📥 Aucune source active, chargement du fichier de config...")
                
                config_path = "/app/config/rss_feeds_global.json"
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        feeds = json.load(f)
                    
                    from urllib.parse import urlparse
                    
                    for feed in feeds:
                        url = feed.get("url")
                        if url:
                            domain = urlparse(url).netloc
                            
                            # Insérer avec UPSERT
                            await db.execute(text("""
                                INSERT INTO sources (name, feed_url, site_domain, method, active)
                                VALUES (:name, :url, :domain, 'rss', true)
                                ON CONFLICT (feed_url) DO UPDATE SET 
                                    active = true,
                                    name = EXCLUDED.name,
                                    site_domain = EXCLUDED.site_domain
                            """), {
                                "name": feed.get("name", domain),
                                "url": url,
                                "domain": domain
                            })
                    
                    await db.commit()
                    
                    # Vérifier le résultat
                    result = await db.execute(text("SELECT COUNT(*) FROM sources WHERE active = true"))
                    new_count = result.scalar()
                    
                    logger.info(f"✅ {new_count} sources chargées depuis le fichier de config")
                else:
                    logger.warning("⚠️ Fichier config RSS non trouvé")
            else:
                logger.info(f"✅ {active_count} sources déjà actives")
            break
            
    except Exception as e:
        logger.error(f"❌ Erreur bootstrap sources: {e}")

# Create FastAPI app
app = FastAPI(
    title="NewsAI API",
    description="API for news collection and analysis with AI",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Global exception on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred",
            "path": str(request.url.path)
        }
    )

# Include routers
app.include_router(routes_health.router)
app.include_router(routes_articles.router, prefix="/api/v1")
app.include_router(routes_sources.router, prefix="/api/v1") 
app.include_router(routes_topics.router, prefix="/api/v1")
app.include_router(routes_clusters.router, prefix="/api/v1")
app.include_router(routes_stats.router, prefix="/api/v1")
app.include_router(routes_search.router, prefix="/api/v1")
app.include_router(routes_sentiment.router, prefix="/api/v1")
app.include_router(routes_summaries.router, prefix="/api/v1")
app.include_router(routes_synthesis.router, prefix="/api/v1")
app.include_router(routes_exports.router, prefix="/api/v1")
app.include_router(routes_graph.router, prefix="/api/v1")
app.include_router(routes_relations.router, prefix="/api/v1")

# Root endpoint
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "NewsAI API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "health": "/health"
    }

# ✅ NOUVEAUX ENDPOINTS ADMIN

@app.get("/api/v1/admin/diagnose")
async def diagnose_system():
    """Diagnostic complet du système"""
    try:
        async for db in get_session():
            # 1. Vérifier les sources
            sources_result = await db.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE active = true) as active,
                    COUNT(*) FILTER (WHERE active = false) as inactive
                FROM sources
            """))
            sources_stats = sources_result.fetchone()
            
            # 2. Vérifier les articles
            articles_result = await db.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE fetched_at >= NOW() - INTERVAL '24 hours') as last_24h,
                    MAX(fetched_at) as last_fetch
                FROM articles
            """))
            articles_stats = articles_result.fetchone()
            
            # 3. Lister quelques sources actives
            active_sources_result = await db.execute(text("""
                SELECT id, name, feed_url, active 
                FROM sources 
                WHERE active = true 
                LIMIT 5
            """))
            active_sources = [dict(r._mapping) for r in active_sources_result.fetchall()]
            
            # 4. Vérifier le fichier de config
            config_exists = os.path.exists("/app/config/rss_feeds_global.json")
            
            return {
                "status": "success",
                "timestamp": datetime.utcnow(),
                "sources": {
                    "total": sources_stats[0],
                    "active": sources_stats[1], 
                    "inactive": sources_stats[2]
                },
                "articles": {
                    "total": articles_stats[0],
                    "last_24h": articles_stats[1],
                    "last_fetch": articles_stats[2]
                },
                "active_sources_sample": active_sources,
                "config_file_exists": config_exists,
                "recommendations": [
                    "✅ Tout semble OK" if sources_stats[1] > 0 else "⚠️ Aucune source active",
                    "✅ Articles récents" if articles_stats[1] > 0 else "⚠️ Pas d'articles récents",
                    "✅ Config trouvée" if config_exists else "❌ Fichier config manquant"
                ]
            }
            
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow()
        }

@app.post("/api/v1/admin/fix-sources")
async def fix_sources():
    """Répare les sources à partir du fichier de config"""
    try:
        async for db in get_session():
            # Réactiver toutes les sources existantes
            await db.execute(text("UPDATE sources SET active = true"))
            
            # Recharger depuis le config si disponible
            config_path = "/app/config/rss_feeds_global.json"
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    feeds = json.load(f)
                
                from urllib.parse import urlparse
                
                for feed in feeds:
                    url = feed.get("url")
                    if url:
                        domain = urlparse(url).netloc
                        await db.execute(text("""
                            INSERT INTO sources (name, feed_url, site_domain, method, active)
                            VALUES (:name, :url, :domain, 'rss', true)
                            ON CONFLICT (feed_url) DO UPDATE SET 
                                active = true,
                                name = EXCLUDED.name,
                                site_domain = EXCLUDED.site_domain
                        """), {
                            "name": feed.get("name", domain),
                            "url": url,
                            "domain": domain
                        })
            
            await db.commit()
            
            # Compter le résultat
            result = await db.execute(text("SELECT COUNT(*) FROM sources WHERE active = true"))
            active_count = result.scalar()
            
            return {
                "status": "success",
                "message": f"Sources réparées: {active_count} sources actives",
                "timestamp": datetime.utcnow()
            }
            
    except Exception as e:
        return {
            "status": "error", 
            "error": str(e),
            "timestamp": datetime.utcnow()
        }

@app.post("/api/v1/admin/collect")
async def manual_collection():
    """Déclenche une collecte manuelle"""
    try:
        async for db in get_session():
            logger.info("🔄 Démarrage de la collecte manuelle...")
            result = await run_collection_once(db)
            
            if CACHE_AVAILABLE and cache:
                try:
                    await cache.invalidate_pattern("api_responses:*")
                    logger.info("✅ Cache invalidé après collecte")
                except:
                    pass
            
            return {
                "status": "success",
                "message": "Collecte manuelle terminée",
                "result": result,
                "cache_cleared": CACHE_AVAILABLE,
                "timestamp": datetime.utcnow()
            }
            
    except Exception as e:
        logger.error(f"❌ Erreur collecte manuelle: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow()
        }

@app.get("/api/v1/admin/collection-status")
async def collection_status():
    """Statut de la collecte automatique"""
    try:
        health = await get_collection_health()
        
        worker_enabled = os.getenv("ENABLE_AUTO_COLLECTION", "true").lower() == "true"
        collection_interval = int(os.getenv("COLLECTION_INTERVAL_MINUTES", "30"))
        
        return {
            "collection_enabled": worker_enabled,
            "interval_minutes": collection_interval,
            "health": health,
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow()
        }

@app.post("/api/v1/admin/process-topics")
async def process_topics_and_clusters(
    limit: int = 50,
    since_hours: int = 24,
    fallback: bool = True,
    db: AsyncSession = Depends(get_session)
):
    """Process articles to extract topics and assign clusters"""
    try:
        from .services.topic_extractor import process_articles_for_topics_and_clusters, process_basic_topics_fallback
        
        # First try LLM-based topic extraction
        result = await process_articles_for_topics_and_clusters(db, limit, since_hours)
        
        # If we need more topics, use fallback method
        if fallback and result["topics_extracted"] < 10:
            fallback_count = await process_basic_topics_fallback(db, limit * 2)
            result["fallback_topics"] = fallback_count
        
        return {
            "status": "success",
            "message": "Topic and cluster processing completed",
            "result": result,
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Topic processing error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow()
        }

@app.post("/api/v1/admin/process-sentiment")
async def process_sentiment_analysis(
    limit: int = 50,
    since_hours: int = 24,
    use_llm: bool = True,
    fallback: bool = True,
    db: AsyncSession = Depends(get_session)
):
    """Process articles to analyze sentiment"""
    try:
        from .services.sentiment_analyzer import process_articles_sentiment, bulk_sentiment_analysis_fallback
        
        # First try LLM-based sentiment analysis
        result = await process_articles_sentiment(db, limit, since_hours, use_llm)
        
        # If we need more sentiment data, use fallback method
        if fallback and result["processed"] < 10:
            fallback_count = await bulk_sentiment_analysis_fallback(db, limit * 2)
            result["fallback_analyzed"] = fallback_count
        
        return {
            "status": "success",
            "message": "Sentiment analysis completed",
            "result": result,
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Sentiment analysis error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow()
        }

# Health endpoint for monitoring
@app.get("/api/v1/system/status")
async def system_status():
    """System status endpoint"""
    try:
        collection_health = await get_collection_health()
        
        return {
            "api": {"status": "healthy"},
            "collection": collection_health,
            "cache": {"available": CACHE_AVAILABLE},
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"System status error: {e}")
        return {
            "api": {"status": "degraded"},
            "error": str(e),
            "timestamp": datetime.utcnow()
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=False,
        log_level="info"
    )