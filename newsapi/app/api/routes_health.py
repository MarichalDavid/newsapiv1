from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core.db import get_session
from datetime import datetime

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    """Health check basique"""
    return {
        "status": "ok", 
        "message": "API NewsAI is running",
        "timestamp": datetime.utcnow()
    }

@router.get("/health/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_session)):
    """Health check détaillé avec base de données"""
    try:
        # Test de connexion simple
        await db.execute(text("SELECT 1"))
        
        # Statistiques de base
        result = await db.execute(text("SELECT COUNT(*) FROM articles"))
        article_count = result.scalar_one()
        
        result2 = await db.execute(text("SELECT COUNT(*) FROM sources WHERE active = TRUE"))
        active_sources = result2.scalar_one()
        
        # Articles récents
        result3 = await db.execute(text("""
            SELECT COUNT(*) FROM articles 
            WHERE fetched_at >= NOW() - INTERVAL '24 hours'
        """))
        recent_articles = result3.scalar_one()
        
        return {
            "status": "ok",
            "database": "connected",
            "articles_count": article_count,
            "active_sources": active_sources,
            "recent_articles_24h": recent_articles,
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        return {
            "status": "error", 
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow()
        }