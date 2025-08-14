from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core.db import get_session

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    """Health check basique"""
    return {"status": "ok", "message": "API NewsAPI is running"}

@router.get("/health/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_session)):
    """Health check détaillé avec stats DB"""
    try:
        # Test de connexion DB
        result = await db.execute(text("SELECT COUNT(*) FROM articles"))
        article_count = result.scalar()
        
        # Stats sources
        source_result = await db.execute(text("SELECT COUNT(*) FROM sources WHERE active = true"))
        active_sources = source_result.scalar()
        
        return {
            "status": "ok",
            "database": "connected",
            "articles_count": article_count,
            "active_sources": active_sources,
            "timestamp": "now()"
        }
    except Exception as e:
        return {
            "status": "error", 
            "database": "disconnected",
            "error": str(e)
        }