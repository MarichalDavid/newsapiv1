from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_session
from ..core.models import Article
from ..services.summarize import llm_summarize, choose_summary

router = APIRouter(tags=["summaries"])

@router.get("/summaries")
async def list_or_regen_summaries(
    since_hours: int = Query(24, ge=1, le=24*14),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    lang: Optional[str] = Query(None, description="Langue de sortie (ex: 'fr' ou 'en')"),
    regen: bool = Query(False, description="Régénérer les résumés manquants/forcés via LLM"),
    persist: bool = Query(False, description="Si true, on enregistre summary_llm + summary_final"),
    db: AsyncSession = Depends(get_session)
):
    now = datetime.utcnow()
    since_dt = now - timedelta(hours=since_hours)

    stmt = (
        select(Article)
        .where(
            or_(
                Article.published_at == None,
                Article.published_at >= since_dt
            )
        )
        # ✅ CORRECTION: desc() doit être à l'intérieur de nulls_last()
        .order_by(
            desc(Article.published_at).nulls_last(),
            desc(Article.id)
        )
        .offset(offset)
        .limit(limit)
    )

    res = await db.execute(stmt)
    articles = list(res.scalars().all())

    out = []
    touched = False

    for a in articles:
        final = a.summary_final
        source = a.summary_source
        llm    = a.summary_llm

        if regen or not final:
            final, source, _ = choose_summary(a.summary_feed, a.full_text)
            if not final:
                raw = a.full_text or a.summary_feed or a.title or ""
                llm_text = await llm_summarize(raw, lang=lang or a.lang or "fr", max_words=180)
                final = llm_text
                source = "llm"
                llm    = llm_text

            if persist:
                a.summary_final = final
                a.summary_source = source
                a.summary_llm = llm
                touched = True

        out.append({
            "id": a.id,
            "source_id": a.source_id,
            "canonical_url": a.canonical_url,
            "domain": a.domain,
            "title": a.title,
            "published_at": a.published_at,
            "lang": a.lang,
            "summary_final": final,
            "summary_source": source,
            "url": a.url,
        })

    if persist and touched:
        await db.commit()

    return out