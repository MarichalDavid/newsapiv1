import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.db import get_session
from ..core.schemas import Filters, ArticleOut, ArticleDetail
from ..services.queries import list_articles, get_article
from pydantic import ValidationError

router = APIRouter(prefix="/articles", tags=["articles"])

@router.get("", response_model=list[ArticleOut])
async def get_articles(
    limit: int = Query(20, ge=1, le=1000, description="Nombre d'articles"),
    offset: int = Query(0, ge=0, description="Décalage"),
    q: str | None = None,
    topic: list[str] | None = None,
    region: list[str] | None = None,
    keywords: list[str] | None = None,
    lang: list[str] | None = None,
    source_id: list[int] | None = None,
    domain: list[str] | None = None,
    date_from: Optional[datetime] = Query(None, description="Date de début"),
    date_to: Optional[datetime] = Query(None, description="Date de fin"),
    has_full_text: bool | None = None,
    summary_source: str | None = None,
    order_by: str = "published_at",
    order: str = "desc",
    db: AsyncSession = Depends(get_session)
):
    try:
        f = Filters(
            q=q, topic=topic, region=region, keywords=keywords, lang=lang, source_id=source_id,
            domain=domain, date_from=date_from, date_to=date_to, has_full_text=has_full_text,
            summary_source=summary_source, order_by=order_by, order=order, limit=limit, offset=offset
        )
        arts = await list_articles(db, f)
        return arts
    except ValidationError as e:
        error_details = []
        for error in e.errors():
            field = error['loc'][-1] if error['loc'] else 'unknown'
            message = error['msg']
            error_details.append(f"{field}: {message}")
        
        raise HTTPException(
            status_code=422,
            detail=f"Paramètres invalides: {'; '.join(error_details)}"
        )
    except Exception as e:
        logging.error(f"Erreur get_articles: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Erreur interne du serveur"
        )


@router.get("/{id}", response_model=ArticleDetail)
async def get_article_by_id(id: int, db: AsyncSession = Depends(get_session)):
    art = await get_article(db, id)
    if not art:
        raise HTTPException(404, "Article not found")
    return art

# ✅ CORRECTION: Un seul endpoint /search avec paramètre obligatoire
@router.get("/search")
async def search_articles_in_articles(
    q: str = Query(..., description="Requête de recherche obligatoire"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    lang: str | None = None,
    domain: str | None = None,
    topic: str | None = None,
    db: AsyncSession = Depends(get_session)
):
    """Recherche d'articles avec paramètres de filtrage"""
    try:
        # Construire les filtres pour la recherche
        topic_list = [topic] if topic else None
        lang_list = [lang] if lang else None
        domain_list = [domain] if domain else None
        
        f = Filters(
            q=q,
            lang=lang_list,
            topic=topic_list,
            domain=domain_list,
            limit=limit,
            offset=offset,
            order_by="published_at",
            order="desc"
        )
        arts = await list_articles(db, f)
        
        return {
            "query": q,
            "filters": {
                "lang": lang,
                "domain": domain, 
                "topic": topic
            },
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total_returned": len(arts)
            },
            "articles": arts
        }
        
    except Exception as e:
        logging.error(f"Erreur search_articles: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Erreur lors de la recherche"
        )