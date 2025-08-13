from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core.db import get_session

router = APIRouter(prefix="/sentiment", tags=["sentiment"])

def since_date(days: int) -> date:
    # J-<days>, en type date Python (évite les concaténations d'intervalles côté SQL)
    return date.today() - timedelta(days=days)

@router.get("/topic/{topic_id}")
async def sentiment_topic(
    topic_id: int = Path(..., ge=1),
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_session),
):
    sql = text("""
        SELECT d, topic_id, pos_count, neu_count, neg_count
        FROM topic_sentiment_daily
        WHERE topic_id = :t
          AND d >= :since
        ORDER BY d DESC
        LIMIT 1000
    """)
    params = {"t": topic_id, "since": since_date(days)}
    rows = (await db.execute(sql, params)).mappings().all()
    return [dict(r) for r in rows]

@router.get("/source/{domain}")
async def sentiment_source(
    domain: str = Path(..., description="domaine ex: www.bbc.com"),
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_session),
):
    domain = domain.strip().lower()  # normalisation simple
    sql = text("""
        SELECT d, domain, pos_count, neu_count, neg_count
        FROM source_sentiment_daily
        WHERE domain = :domain
          AND d >= :since
        ORDER BY d DESC
        LIMIT 1000
    """)
    params = {"domain": domain, "since": since_date(days)}
    rows = (await db.execute(sql, params)).mappings().all()
    return [dict(r) for r in rows]
