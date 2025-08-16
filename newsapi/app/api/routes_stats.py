from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core.db import get_session
from datetime import datetime, timedelta

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/general")
async def general_stats(db: AsyncSession = Depends(get_session)):
    """Statistiques générales de l'API"""
    # ✅ CORRECTION: Utiliser une date calculée côté Python
    since_24h = datetime.utcnow() - timedelta(hours=24)
    
    sql = text("""
        SELECT 
            COUNT(*) as total_articles,
            COUNT(DISTINCT domain) as unique_domains,
            COUNT(DISTINCT cluster_id) as total_clusters,
            COUNT(*) FILTER (WHERE published_at >= :since_24h) as articles_24h
        FROM articles
    """)
    
    result = (await db.execute(sql, {"since_24h": since_24h})).mappings().first()
    return dict(result)

@router.get("/sources")
async def sources_stats(db: AsyncSession = Depends(get_session)):
    """Statistiques par source"""
    sql = text("""
        SELECT 
            s.name,
            s.site_domain,
            COUNT(a.id) as article_count,
            MAX(a.published_at) as last_article
        FROM sources s
        LEFT JOIN articles a ON s.id = a.source_id
        WHERE s.active = true
        GROUP BY s.id, s.name, s.site_domain
        ORDER BY article_count DESC
        LIMIT 20
    """)
    
    rows = (await db.execute(sql)).mappings().all()
    return [dict(r) for r in rows]

@router.get("/topics")
async def topics_stats(db: AsyncSession = Depends(get_session)):
    """Statistiques par topic"""
    # ✅ CORRECTION: Utiliser une date calculée côté Python
    since_7d = datetime.utcnow() - timedelta(days=7)
    
    sql = text("""
        SELECT 
            unnest(topics) AS topic,
            COUNT(*) AS article_count,
            COUNT(*) FILTER (WHERE published_at >= :since_7d) as recent_count
        FROM articles
        WHERE topics IS NOT NULL
        GROUP BY topic
        ORDER BY article_count DESC
        LIMIT 50
    """)
    
    rows = (await db.execute(sql, {"since_7d": since_7d})).mappings().all()
    return [dict(r) for r in rows]

@router.get("/timeline")
async def timeline_stats(
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_session)
):
    """Timeline des statistiques"""
    # ✅ CORRECTION: Calculer la date côté Python
    since_dt = datetime.utcnow() - timedelta(days=days)
    
    sql = text("""
        SELECT 
            DATE(published_at) as date,
            COUNT(*) as article_count,
            COUNT(DISTINCT domain) as source_count
        FROM articles
        WHERE published_at >= :since_dt
        GROUP BY DATE(published_at)
        ORDER BY date DESC
    """)
    
    rows = (await db.execute(sql, {"since_dt": since_dt})).mappings().all()
    return [dict(r) for r in rows]