from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core.db import get_session
from datetime import datetime, timedelta

router = APIRouter(prefix="/clusters", tags=["clusters"])

@router.get("")
async def list_clusters(
    since_hours: int = Query(48, ge=1, le=168),
    limit_clusters: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_session)
):
    # ✅ CORRECTION: Calculer la date côté Python
    since_dt = datetime.utcnow() - timedelta(hours=since_hours)
    
    sql = text("""
        WITH recent AS (
          SELECT cluster_id, count(*) AS n, max(published_at) AS last_pub
          FROM articles
          WHERE fetched_at >= :since_dt
            AND cluster_id IS NOT NULL
          GROUP BY cluster_id
        )
        SELECT * FROM recent
        ORDER BY n DESC, last_pub DESC
        LIMIT :limit_clusters
    """)
    
    res = await db.execute(sql, {
        "since_dt": since_dt,
        "limit_clusters": limit_clusters
    })
    
    # ✅ CORRECTION: Utiliser .mappings() correctement
    return [dict(r) for r in res.mappings()]

@router.get("/{cluster_id}/articles")
async def articles_in_cluster(
    cluster_id: str, 
    limit: int = Query(50, ge=1, le=1000), 
    offset: int = Query(0, ge=0), 
    db: AsyncSession = Depends(get_session)
):
    sql = text("""
        SELECT id, title, url, canonical_url, domain, published_at, lang, keywords, topics, summary_final, summary_source
        FROM articles
        WHERE cluster_id = :cid
        ORDER BY published_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """)
    
    res = await db.execute(sql, {
        "cid": cluster_id, 
        "limit": limit, 
        "offset": offset
    })
    
    # ✅ CORRECTION: Utiliser .mappings() correctement
    return [dict(r) for r in res.mappings()]

@router.get("/{cluster_id}")
async def get_cluster_details(
    cluster_id: str, 
    db: AsyncSession = Depends(get_session)
):
    """Détails d'un cluster spécifique"""
    sql = text("""
        SELECT COUNT(*) as article_count,
               MIN(published_at) as first_article,
               MAX(published_at) as last_article,
               array_agg(DISTINCT domain) as domains
        FROM articles
        WHERE cluster_id = :cluster_id
        GROUP BY cluster_id
    """)
    
    result = (await db.execute(sql, {"cluster_id": cluster_id})).mappings().first()
    
    if not result or result['article_count'] == 0:
        raise HTTPException(404, f"Cluster '{cluster_id}' not found")
    
    return {
        "cluster_id": cluster_id,
        "article_count": result['article_count'],
        "first_article": result['first_article'],
        "last_article": result['last_article'],
        "domains": result['domains']
    }