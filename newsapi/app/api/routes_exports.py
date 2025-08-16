from fastapi import APIRouter, Depends, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.db import get_session
from ..core.schemas import Filters
from ..services.queries import list_articles
from sqlalchemy import text
from datetime import datetime, timedelta

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

@router.get("/sentiment.csv")
async def export_sentiment_csv(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_session)
):
    """Export CSV des données de sentiment"""
    since_dt = datetime.utcnow() - timedelta(days=days)
    
    # Query actual articles table for sentiment data
    sql = text("""
        SELECT 
            DATE(published_at) as date,
            domain,
            COUNT(*) as total_articles,
            COUNT(*) FILTER (WHERE sentiment_score > 0.1) as positive,
            COUNT(*) FILTER (WHERE sentiment_score BETWEEN -0.1 AND 0.1) as neutral,
            COUNT(*) FILTER (WHERE sentiment_score < -0.1) as negative,
            AVG(sentiment_score) as avg_sentiment
        FROM articles
        WHERE published_at >= :since_dt
        AND sentiment_score IS NOT NULL
        GROUP BY DATE(published_at), domain
        ORDER BY date DESC, domain
    """)
    
    rows = (await db.execute(sql, {"since_dt": since_dt})).mappings().all()
    
    csv_rows = ["date,domain,total_articles,positive,neutral,negative,avg_sentiment"]
    for r in rows:
        csv_rows.append(f"{r['date']},{r['domain']},{r['total_articles']},{r['positive']},{r['neutral']},{r['negative']},{r['avg_sentiment']:.3f}")
    
    return Response(content="\n".join(csv_rows), media_type="text/csv")

@router.get("/topics.json")
async def export_topics_json(db: AsyncSession = Depends(get_session)):
    """Export JSON des topics"""
    sql = text("""
        SELECT unnest(topics) AS topic, COUNT(*) AS count
        FROM articles
        WHERE topics IS NOT NULL
        GROUP BY topic
        ORDER BY count DESC
    """)
    
    rows = (await db.execute(sql)).mappings().all()
    return [dict(r) for r in rows]

@router.get("/stats.json")
async def export_stats_json(db: AsyncSession = Depends(get_session)):
    """Export JSON des statistiques"""
    sql = text("""
        SELECT 
            COUNT(*) as total_articles,
            COUNT(DISTINCT domain) as unique_domains,
            COUNT(DISTINCT cluster_id) as total_clusters
        FROM articles
    """)
    
    result = (await db.execute(sql)).mappings().first()
    return dict(result)