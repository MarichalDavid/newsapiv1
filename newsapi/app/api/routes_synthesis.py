from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, and_, or_, func, cast, String
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_session
from ..core.models import Article
from ..services.summarize import llm_synthesis_from_docs

router = APIRouter(tags=["synthesis"])

@router.get("/synthesis")
async def synthesis_endpoint(
    q: Optional[str] = Query(None, description="Mot-clé plein texte (titre|summary|full_text)"),
    source_id: Optional[int] = Query(None, ge=1),
    topic: Optional[str] = Query(None, description="ex: 'tech', 'politique'… si alimenté"),
    since_hours: int = Query(24, ge=1, le=24*30),
    limit_docs: int = Query(30, ge=5, le=120),
    lang: str = Query("fr"),
    db: AsyncSession = Depends(get_session),
):
    now = datetime.utcnow()
    since_dt = now - timedelta(hours=since_hours)

    conds = [
        or_(Article.published_at == None, Article.published_at >= since_dt)
    ]

    if source_id:
        conds.append(Article.source_id == source_id)

    if topic:
        # Adapte selon le type réel de Article.topics (TEXT/ARRAY/JSONB)
        #conds.append(func.cast(Article.topics, str).ilike(f"%{topic}%"))
        conds.append(cast(Article.topics, String).ilike(f"%{topic}%"))

    if q:
        like = f"%{q}%"
        conds.append(
            or_(
                Article.title.ilike(like),
                Article.summary_feed.ilike(like),
                Article.full_text.ilike(like),
            )
        )

    stmt = (
        select(Article)
        .where(and_(*conds))
        # ✅ CORRECTION: desc() doit être à l'intérieur de nulls_last()
        .order_by(
            desc(Article.published_at).nulls_last(),
            desc(Article.id)
        )
        .limit(limit_docs)
    )

    res = await db.execute(stmt)
    rows = list(res.scalars().all())

    if not rows:
        raise HTTPException(status_code=404, detail="Aucun article ne correspond aux filtres.")

    docs = []
    for a in rows:
        summ = a.summary_final or a.summary_feed or (a.full_text[:400] if a.full_text else "") or a.title
        docs.append({
            "title": a.title or "(untitled)",
            "summary": summ or "",
            "url": a.canonical_url or a.url,
            "published_at": a.published_at,
            "domain": a.domain,
        })

    text = await llm_synthesis_from_docs(docs, lang=lang, max_words=260)

    return {
        "filters": {
            "q": q, "source_id": source_id, "topic": topic,
            "since_hours": since_hours,
            "limit_docs": limit_docs,
            "lang": lang
        },
        "docs_count": len(docs),
        "synthesis": text,
        "sample_articles": [
            {"title": d["title"], "url": d["url"], "published_at": d["published_at"]}
            for d in docs[:8]
        ]
    }