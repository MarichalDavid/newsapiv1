from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.db import get_session
from ..core.models import Source
from ..core.schemas import SourceOut
from sqlalchemy import select, insert, delete
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
