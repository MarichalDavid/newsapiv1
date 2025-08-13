from sqlalchemy import select, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.models import Article
from ..core.schemas import Filters

def _order_clause(order_by: str, order: str):
    col = getattr(Article, order_by if order_by in {"published_at","fetched_at"} else "published_at")
    return desc(col) if (order or "desc").lower() == "desc" else asc(col)

async def list_articles(db: AsyncSession, f: Filters):
    q = select(Article)
    if f.q:
        like = f"%{f.q}%"
        q = q.where(or_(Article.title.ilike(like), Article.summary_final.ilike(like)))
    if f.keywords:
        for kw in f.keywords:
            q = q.where(Article.keywords.any(kw))
    if f.lang:
        q = q.where(Article.lang.in_(f.lang))
    if f.source_id:
        q = q.where(Article.source_id.in_(f.source_id))
    if f.domain:
        q = q.where(Article.domain.in_(f.domain))
    if f.date_from:
        q = q.where(Article.published_at >= f.date_from)
    if f.date_to:
        q = q.where(Article.published_at <= f.date_to)
    if f.has_full_text is True:
        q = q.where(Article.full_text.is_not(None))
    if f.has_full_text is False:
        q = q.where(Article.full_text.is_(None))
    if f.summary_source:
        q = q.where(Article.summary_source == f.summary_source)

    q = q.order_by(_order_clause(f.order_by or "published_at", f.order or "desc")).limit(f.limit).offset(f.offset)
    res = await db.execute(q)
    return res.scalars().all()

async def get_article(db: AsyncSession, id: int):
    res = await db.execute(select(Article).where(Article.id == id))
    return res.scalar_one_or_none()
