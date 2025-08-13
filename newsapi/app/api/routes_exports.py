from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.db import get_session
from ..core.schemas import Filters
from ..services.queries import list_articles

router = APIRouter(prefix="/exports", tags=["exports"])

@router.get("/articles.csv")
async def export_articles_csv(
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
    limit: int = 1000,
    offset: int = 0,
    db: AsyncSession = Depends(get_session)
):
    f = Filters(
        q=q, topic=topic, region=region, keywords=keywords, lang=lang, source_id=source_id,
        domain=domain, date_from=date_from, date_to=date_to, has_full_text=has_full_text,
        summary_source=summary_source, order_by=order_by, order=order, limit=limit, offset=offset
    )
    arts = await list_articles(db, f)
    rows = ["id,title,domain,canonical_url,published_at,lang,summary_source,keywords,topics"]
    def csvsafe(s):
        if s is None: return ""
        s = str(s).replace('"','""').replace('\n',' ').replace('\r',' ')
        return f'"{s}"'
    for a in arts:
        rows.append(",".join([
            str(a.id),
            csvsafe(a.title),
            csvsafe(a.domain),
            csvsafe(a.canonical_url),
            csvsafe(a.published_at),
            csvsafe(a.lang),
            csvsafe(a.summary_source),
            csvsafe(";".join(a.keywords or [])),
            csvsafe(";".join(a.topics or []))
        ]))
    return Response(content="\n".join(rows), media_type="text/csv")
