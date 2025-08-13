from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core.db import get_session

router = APIRouter(prefix="/clusters", tags=["clusters"])

@router.get("")
async def list_clusters(since_hours: int = 48, limit_clusters: int = 100, db: AsyncSession = Depends(get_session)):
    sql = text("""
        WITH recent AS (
          SELECT cluster_id, count(*) AS n, max(published_at) AS last_pub
          FROM articles
          WHERE fetched_at >= NOW() - (:since_hours || ' hours')::interval
            AND cluster_id IS NOT NULL
          GROUP BY cluster_id
        )
        SELECT * FROM recent
        ORDER BY n DESC, last_pub DESC
        LIMIT :limit_clusters
    """)
    res = await db.execute(sql, {"since_hours": since_hours, "limit_clusters": limit_clusters})
    return [dict(r) for r in res]

@router.get("/{cluster_id}/articles")
async def articles_in_cluster(cluster_id: str, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_session)):
    sql = text("""
        SELECT id, title, canonical_url, domain, published_at, lang, keywords, topics, summary_final, summary_source
        FROM articles
        WHERE cluster_id = :cid
        ORDER BY published_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """)
    res = await db.execute(sql, {"cid": cluster_id, "limit": limit, "offset": offset})
    return [dict(r) for r in res]
