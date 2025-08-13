from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.db import get_session
from ..core.schemas import Filters, ArticleOut, ArticleDetail
from ..services.queries import list_articles, get_article

router = APIRouter(prefix="/articles", tags=["articles"])

@router.get("", response_model=list[ArticleOut])
async def get_articles(
    q: str | None = None,
    topic: list[str] | None = None,
    region: list[str] | None = None,
    keywords: list[str] | None = None,
    lang: list[str] | None = None,
    source_id: list[int] | None = None,
    domain: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    has_full_text: bool | None = None,
    summary_source: str | None = None,
    order_by: str = "published_at",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_session)
):
    f = Filters(
        q=q, topic=topic, region=region, keywords=keywords, lang=lang, source_id=source_id,
        domain=domain, date_from=date_from, date_to=date_to, has_full_text=has_full_text,
        summary_source=summary_source, order_by=order_by, order=order, limit=limit, offset=offset
    )
    arts = await list_articles(db, f)
    return arts

@router.get("/{id}", response_model=ArticleDetail)
async def get_article_by_id(id: int, db: AsyncSession = Depends(get_session)):
    art = await get_article(db, id)
    if not art:
        raise HTTPException(404, "Article not found")
    return art
