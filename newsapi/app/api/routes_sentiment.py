from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core.db import get_session

router = APIRouter(prefix="/sentiment", tags=["sentiment"])

def since_date(days: int) -> date:
    # J-<days>, en type date Python (évite les concaténations d'intervalles côté SQL)
    return date.today() - timedelta(days=days)

# ✅ NOUVEAU: Sentiment global
@router.get("/global")
async def sentiment_global(
    days: int = Query(7, ge=1, le=90, description="Période en jours"),
    granularity: str = Query("daily", description="daily ou weekly"),
    db: AsyncSession = Depends(get_session),
):
    """Sentiment global de tous les articles"""
    
    if granularity == "weekly":
        # Agrégation par semaine
        sql = text("""
            SELECT 
                DATE_TRUNC('week', published_at) as period,
                COUNT(*) as total_articles,
                AVG(sentiment_score) as avg_sentiment,
                COUNT(*) FILTER (WHERE sentiment_score > 0.1) as positive_count,
                COUNT(*) FILTER (WHERE sentiment_score BETWEEN -0.1 AND 0.1) as neutral_count,
                COUNT(*) FILTER (WHERE sentiment_score < -0.1) as negative_count
            FROM articles
            WHERE published_at >= :since_date
              AND sentiment_score IS NOT NULL
            GROUP BY DATE_TRUNC('week', published_at)
            ORDER BY period DESC
            LIMIT 20
        """)
    else:
        # Agrégation par jour (défaut)
        sql = text("""
            SELECT 
                DATE(published_at) as period,
                COUNT(*) as total_articles,
                AVG(sentiment_score) as avg_sentiment,
                COUNT(*) FILTER (WHERE sentiment_score > 0.1) as positive_count,
                COUNT(*) FILTER (WHERE sentiment_score BETWEEN -0.1 AND 0.1) as neutral_count,
                COUNT(*) FILTER (WHERE sentiment_score < -0.1) as negative_count
            FROM articles
            WHERE published_at >= :since_date
              AND sentiment_score IS NOT NULL
            GROUP BY DATE(published_at)
            ORDER BY period DESC
            LIMIT :days
        """)
    
    params = {"since_date": since_date(days), "days": days}
    rows = (await db.execute(sql, params)).mappings().all()
    
    # Calculer les statistiques globales
    if rows:
        total_articles = sum(r['total_articles'] for r in rows)
        total_positive = sum(r['positive_count'] for r in rows)
        total_neutral = sum(r['neutral_count'] for r in rows)
        total_negative = sum(r['negative_count'] for r in rows)
        
        overall_sentiment = sum(r['avg_sentiment'] * r['total_articles'] for r in rows) / total_articles if total_articles > 0 else 0
        
        global_stats = {
            "period_days": days,
            "granularity": granularity,
            "total_articles": total_articles,
            "overall_sentiment_score": round(overall_sentiment, 3),
            "sentiment_distribution": {
                "positive": total_positive,
                "neutral": total_neutral,
                "negative": total_negative,
                "positive_pct": round((total_positive / total_articles) * 100, 1) if total_articles > 0 else 0,
                "neutral_pct": round((total_neutral / total_articles) * 100, 1) if total_articles > 0 else 0,
                "negative_pct": round((total_negative / total_articles) * 100, 1) if total_articles > 0 else 0,
            }
        }
    else:
        global_stats = {
            "period_days": days,
            "granularity": granularity,
            "total_articles": 0,
            "overall_sentiment_score": 0,
            "sentiment_distribution": {
                "positive": 0, "neutral": 0, "negative": 0,
                "positive_pct": 0, "neutral_pct": 0, "negative_pct": 0
            }
        }
    
    return {
        "global_sentiment": global_stats,
        "daily_breakdown": [dict(r) for r in rows]
    }

@router.get("/topic/{topic_id}")
async def sentiment_topic(
    topic_id: int = Path(..., ge=1),
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_session),
):
    sql = text("""
        SELECT d, topic_id, pos_count, neu_count, neg_count
        FROM topic_sentiment_daily
        WHERE topic_id = :t
          AND d >= :since
        ORDER BY d DESC
        LIMIT 1000
    """)
    params = {"t": topic_id, "since": since_date(days)}
    rows = (await db.execute(sql, params)).mappings().all()
    return [dict(r) for r in rows]

@router.get("/source/{domain}")
async def sentiment_source(
    domain: str = Path(..., description="domaine ex: www.bbc.com"),
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_session),
):
    domain = domain.strip().lower()  # normalisation simple
    sql = text("""
        SELECT d, domain, pos_count, neu_count, neg_count
        FROM source_sentiment_daily
        WHERE domain = :domain
          AND d >= :since
        ORDER BY d DESC
        LIMIT 1000
    """)
    params = {"domain": domain, "since": since_date(days)}
    rows = (await db.execute(sql, params)).mappings().all()
    return [dict(r) for r in rows]