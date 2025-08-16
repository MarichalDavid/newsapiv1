from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_session
from ..core.models import Article
from ..services.summarize import llm_summarize, choose_summary

router = APIRouter(prefix="/summaries", tags=["summaries"])

@router.get("")
async def list_or_regen_summaries(
    since_hours: int = Query(24, ge=1, le=24*14),
    limit: int = Query(10, ge=1, le=50),  # Reduced limit for faster processing
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

    # Limit LLM processing to prevent timeouts
    llm_processed = 0
    max_llm_calls = 5  # Limit concurrent LLM calls
    
    for a in articles:
        final = a.summary_final
        source = a.summary_source
        llm    = a.summary_llm

        if regen or not final:
            final, source, _ = choose_summary(a.summary_feed, a.full_text)
            if not final and llm_processed < max_llm_calls:
                raw = a.full_text or a.summary_feed or a.title or ""
                llm_text = await llm_summarize(raw, lang=lang or a.lang or "fr", max_words=120)  # Reduced tokens
                final = llm_text
                source = "llm"
                llm    = llm_text
                llm_processed += 1
            elif not final:
                # Fallback without LLM for remaining items
                final = (a.summary_feed or a.title or "No summary available")[:200]
                source = "fallback"

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

# ✅ NOUVEAUX ENDPOINTS POUR LES SYNTHÈSES

@router.get("/general")
async def general_summary(
    since_hours: int = Query(24, ge=1, le=24*7, description="Période en heures"),
    target_sentences: int = Query(10, ge=5, le=50, description="Nombre de phrases cibles"),
    lang: str = Query("fr", description="Langue de sortie"),
    db: AsyncSession = Depends(get_session)
):
    """Synthèse générale de l'actualité"""
    from ..services.summarize import llm_synthesis_from_docs
    
    since_dt = datetime.utcnow() - timedelta(hours=since_hours)
    
    # Récupérer les articles récents
    stmt = (
        select(Article)
        .where(Article.published_at >= since_dt)
        .order_by(desc(Article.published_at))
        .limit(20)  # Reduced for faster processing with Qwen2.5:3B
    )
    
    result = await db.execute(stmt)
    articles = result.scalars().all()
    
    if not articles:
        raise HTTPException(404, "Aucun article trouvé pour la période demandée")
    
    # Préparer les documents pour la synthèse
    docs = []
    for article in articles:
        summary = (article.summary_final or 
                  article.summary_feed or 
                  (article.full_text[:400] if article.full_text else "") or 
                  article.title)
        
        docs.append({
            "title": article.title or "(sans titre)",
            "summary": summary,
            "url": article.canonical_url or article.url,
            "published_at": article.published_at,
            "domain": article.domain,
        })
    
    # Générer la synthèse
    max_words = target_sentences * 15  # ~15 mots par phrase
    synthesis_text = await llm_synthesis_from_docs(docs, lang=lang, max_words=max_words)
    
    return {
        "synthesis": synthesis_text,
        "period_hours": since_hours,
        "articles_analyzed": len(articles),
        "language": lang,
        "generated_at": datetime.utcnow(),
    }

@router.get("/topic/{topic_name}")
async def topic_summary(
    topic_name: str,
    since_hours: int = Query(48, ge=1, le=24*7),
    target_sentences: int = Query(8, ge=3, le=30),
    lang: str = Query("fr"),
    db: AsyncSession = Depends(get_session)
):
    """Synthèse pour un topic spécifique"""
    from ..services.summarize import llm_synthesis_from_docs
    from sqlalchemy import cast, String
    
    since_dt = datetime.utcnow() - timedelta(hours=since_hours)
    
    # Rechercher les articles du topic
    stmt = (
        select(Article)
        .where(
            Article.published_at >= since_dt,
            cast(Article.topics, String).ilike(f"%{topic_name}%")
        )
        .order_by(desc(Article.published_at))
        .limit(30)
    )
    
    result = await db.execute(stmt)
    articles = result.scalars().all()
    
    if not articles:
        raise HTTPException(404, f"Aucun article trouvé pour le topic '{topic_name}'")
    
    docs = []
    for article in articles:
        summary = (article.summary_final or 
                  article.summary_feed or 
                  (article.full_text[:400] if article.full_text else "") or 
                  article.title)
        
        docs.append({
            "title": article.title or "(sans titre)",
            "summary": summary,
            "url": article.canonical_url or article.url,
            "published_at": article.published_at,
            "domain": article.domain,
        })
    
    max_words = target_sentences * 15
    synthesis_text = await llm_synthesis_from_docs(docs, lang=lang, max_words=max_words)
    
    return {
        "topic": topic_name,
        "synthesis": synthesis_text,
        "period_hours": since_hours,
        "articles_analyzed": len(articles),
        "language": lang,
        "generated_at": datetime.utcnow(),
    }

@router.get("/source/{domain}")
async def source_summary(
    domain: str,
    since_hours: int = Query(48, ge=1, le=24*7),
    target_sentences: int = Query(8, ge=3, le=30),
    lang: str = Query("fr"),
    db: AsyncSession = Depends(get_session)
):
    """Synthèse pour une source spécifique"""
    from ..services.summarize import llm_synthesis_from_docs
    
    since_dt = datetime.utcnow() - timedelta(hours=since_hours)
    domain = domain.strip().lower()
    
    stmt = (
        select(Article)
        .where(
            Article.published_at >= since_dt,
            Article.domain == domain
        )
        .order_by(desc(Article.published_at))
        .limit(30)
    )
    
    result = await db.execute(stmt)
    articles = result.scalars().all()
    
    if not articles:
        raise HTTPException(404, f"Aucun article trouvé pour la source '{domain}'")
    
    docs = []
    for article in articles:
        summary = (article.summary_final or 
                  article.summary_feed or 
                  (article.full_text[:400] if article.full_text else "") or 
                  article.title)
        
        docs.append({
            "title": article.title or "(sans titre)",
            "summary": summary,
            "url": article.canonical_url or article.url,
            "published_at": article.published_at,
            "domain": article.domain,
        })
    
    max_words = target_sentences * 15
    synthesis_text = await llm_synthesis_from_docs(docs, lang=lang, max_words=max_words)
    
    return {
        "source": domain,
        "synthesis": synthesis_text,
        "period_hours": since_hours,
        "articles_analyzed": len(articles),
        "language": lang,
        "generated_at": datetime.utcnow(),
    }

@router.get("/trending")
async def trending_topics_summary(
    since_hours: int = Query(24, ge=1, le=168),
    min_articles: int = Query(3, ge=2, le=50),
    limit_topics: int = Query(10, ge=5, le=20),
    lang: str = Query("fr"),
    db: AsyncSession = Depends(get_session)
):
    """Synthèse des topics en tendance (fallback sur keywords si topics[] vide)"""
    from sqlalchemy import text
    from datetime import datetime, timedelta

    since_dt = datetime.utcnow() - timedelta(hours=since_hours)

    sql = text("""
        WITH base AS (
            -- 1) topics[] quand présent
            SELECT unnest(topics) AS topic
            FROM articles
            WHERE published_at >= :since_dt
              AND topics IS NOT NULL AND array_length(topics,1) > 0
            UNION ALL
            -- 2) fallback sur keywords[] quand topics[] absent/vide
            SELECT unnest(keywords) AS topic
            FROM articles
            WHERE published_at >= :since_dt
              AND (topics IS NULL OR array_length(topics,1) = 0)
              AND keywords IS NOT NULL AND array_length(keywords,1) > 0
        )
        SELECT topic, COUNT(*) AS article_count
        FROM base
        GROUP BY topic
        HAVING COUNT(*) >= :min_articles
        ORDER BY article_count DESC
        LIMIT :limit_topics
    """)

    params = {
        "since_dt": since_dt,
        "min_articles": min_articles,
        "limit_topics": limit_topics
    }
    result = await db.execute(sql, params)
    rows = result.mappings().all()

    topics_summary = [
        {
            "topic": r["topic"],
            "article_count": r["article_count"],
            "trend_score": r["article_count"] / max(1, since_hours)  # articles/heure
        }
        for r in rows
    ]

    # ✅ Ne JAMAIS lever un 404 ici : renvoyer 200 + liste vide
    return {
        "trending_topics": topics_summary,
        "period_hours": since_hours,
        "total_trending_topics": len(topics_summary),
        "language": lang,
        "generated_at": datetime.utcnow(),
    }
