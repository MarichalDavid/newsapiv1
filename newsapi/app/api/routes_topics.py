from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core.db import get_session

router = APIRouter(prefix="/topics", tags=["topics"])

@router.get("")
async def list_topics(db: AsyncSession = Depends(get_session)):
    sql = text("""
        SELECT unnest(topics) AS topic, COUNT(*) AS count
        FROM articles
        WHERE topics IS NOT NULL
        GROUP BY topic
        ORDER BY count DESC
        LIMIT 200;
    """)
    res = await db.execute(sql)
    rows = res.mappings().all()
    return rows

@router.get("/{topic}/articles")
async def articles_by_topic(topic: str, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_session)):
    sql = text("""
        SELECT id, title, canonical_url, domain, published_at, lang, keywords, topics, summary_final, summary_source
        FROM articles
        WHERE topics @> ARRAY[:topic]
        ORDER BY published_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """)
    res = await db.execute(sql, {"topic": topic, "limit": limit, "offset": offset})
    return [dict(r) for r in res]
