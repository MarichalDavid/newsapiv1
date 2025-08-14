from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.db import get_session
from ..core.models import Source
from ..core.schemas import SourceOut
from sqlalchemy import select, insert, delete, text
import json, os
from urllib.parse import urlparse

router = APIRouter(prefix="/sources", tags=["sources"])

@router.get("", response_model=list[SourceOut])
async def list_sources(db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(Source))
    return res.scalars().all()

@router.post("/refresh")
async def refresh_sources(db: AsyncSession = Depends(get_session)):
    path = os.path.join(os.getcwd(), "config", "rss_feeds_global.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    await db.execute(delete(Source))
    for it in data:
        feed_url = it["url"]
        site_domain = urlparse(feed_url).netloc
        await db.execute(insert(Source).values(
            name=it["name"],
            feed_url=feed_url,
            site_domain=site_domain,
            method="rss",
            enrichment="html",
            frequency_minutes=10,
            active=True
        ))
    await db.commit()
    return {"status":"ok","count":len(data)}

@router.get("/{source_id}")
async def get_source_details(
    source_id: int, 
    db: AsyncSession = Depends(get_session)
):
    """Détails d'une source spécifique"""
    # Récupérer la source
    source_result = await db.execute(
        select(Source).where(Source.id == source_id)
    )
    source = source_result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(404, f"Source {source_id} not found")
    
    # Stats de la source
    sql_stats = text("""
        SELECT COUNT(*) as article_count,
               MAX(published_at) as last_article_date
        FROM articles
        WHERE source_id = :source_id
    """)
    
    stats = (await db.execute(sql_stats, {"source_id": source_id})).fetchone()
    
    return {
        "id": source.id,
        "name": source.name,
        "feed_url": source.feed_url,
        "site_domain": source.site_domain,
        "active": source.active,
        "article_count": stats[0],
        "last_article_date": stats[1]
    }