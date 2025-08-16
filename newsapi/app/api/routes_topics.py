from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core.db import get_session

router = APIRouter(prefix="/topics", tags=["topics"])

@router.get("")
async def list_topics(db: AsyncSession = Depends(get_session)):
    # 1) topics[] si présent
    # 2) sinon fallback sur keywords[]
    sql = text("""
        WITH base AS (
            SELECT unnest(topics) AS topic
            FROM articles
            WHERE topics IS NOT NULL AND array_length(topics,1) > 0
            UNION ALL
            SELECT unnest(keywords) AS topic
            FROM articles
            WHERE (topics IS NULL OR array_length(topics,1) = 0)
              AND keywords IS NOT NULL AND array_length(keywords,1) > 0
        )
        SELECT topic, COUNT(*) AS count
        FROM base
        GROUP BY topic
        ORDER BY count DESC
        LIMIT 100
    """)
    rows = (await db.execute(sql)).mappings().all()
    return [dict(r) for r in rows]

@router.get("/{topic}/articles")
async def articles_by_topic(topic: str, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_session)):
    sql = text("""
        SELECT id, title, url, canonical_url, domain, published_at, lang, keywords, topics, summary_final, summary_source
        FROM articles
        WHERE topics && ARRAY[:topic]
        ORDER BY published_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """)
    res = await db.execute(sql, {"topic": topic, "limit": limit, "offset": offset})
    rows = res.mappings().all()
    return [dict(r) for r in rows]

@router.get("/{topic_name}")
async def get_topic_details(
    topic_name: str, 
    db: AsyncSession = Depends(get_session)
):
    """Détails d'un topic spécifique"""
    # Récupérer stats du topic
    sql_stats = text("""
        SELECT COUNT(*) as article_count
        FROM articles
        WHERE topics @> ARRAY[:topic]
    """)
    
    # Récupérer articles récents du topic
    sql_articles = text("""
        SELECT id, title, canonical_url, domain, published_at
        FROM articles
        WHERE topics @> ARRAY[:topic]
        ORDER BY published_at DESC NULLS LAST
        LIMIT 5
    """)
    
    stats = (await db.execute(sql_stats, {"topic": topic_name})).fetchone()
    articles = (await db.execute(sql_articles, {"topic": topic_name})).mappings().all()
    
    if stats[0] == 0:
        raise HTTPException(404, f"Topic '{topic_name}' not found")
    
    return {
        "topic": topic_name,
        "article_count": stats[0],
        "recent_articles": [dict(r) for r in articles]
    }