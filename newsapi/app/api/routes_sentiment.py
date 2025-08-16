from datetime import date, timedelta, datetime
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core.db import get_session

router = APIRouter(prefix="/sentiment", tags=["sentiment"])

def since_date(days: int) -> date:
    # J-<days>, en type date Python (évite les concaténations d'intervalles côté SQL)
    return date.today() - timedelta(days=days)

@router.get("/global")
async def sentiment_global(
    days: int = Query(7, ge=1, le=90, description="Période en jours"),
    granularity: str = Query("daily", description="daily ou weekly"),
    db: AsyncSession = Depends(get_session),
):
    """Sentiment global de tous les articles"""
    
    # ✅ CORRECTION: Calculer la date côté Python
    since_dt = datetime.utcnow() - timedelta(days=days)
    
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
            WHERE published_at >= :since_dt
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
            WHERE published_at >= :since_dt
              AND sentiment_score IS NOT NULL
            GROUP BY DATE(published_at)
            ORDER BY period DESC
            LIMIT :days
        """)
    
    params = {"since_dt": since_dt, "days": days}
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

@router.get("/topics")
async def list_sentiment_topics(
    db: AsyncSession = Depends(get_session),
):
    """List all available topics with sentiment data"""
    sql = text("""
        SELECT 
            unnest(topics) as topic,
            COUNT(*) as article_count,
            AVG(sentiment_score) as avg_sentiment,
            COUNT(*) FILTER (WHERE sentiment_score > 0.1) as positive_count,
            COUNT(*) FILTER (WHERE sentiment_score BETWEEN -0.1 AND 0.1) as neutral_count,
            COUNT(*) FILTER (WHERE sentiment_score < -0.1) as negative_count
        FROM articles 
        WHERE topics IS NOT NULL 
        AND sentiment_score IS NOT NULL
        GROUP BY unnest(topics)
        ORDER BY article_count DESC
        LIMIT 50
    """)
    
    rows = (await db.execute(sql)).mappings().all()
    return [dict(r) for r in rows]

@router.get("/topic/{topic_identifier}")
async def sentiment_topic(
    topic_identifier: str = Path(..., description="Topic name or topic number (1-based index from topics list)"),
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_session),
):
    """Get sentiment analysis for a specific topic by name or number"""
    since_dt = datetime.utcnow() - timedelta(days=days)
    
    # Check if topic_identifier is numeric (topic index)
    topic_name = topic_identifier
    if topic_identifier.isdigit():
        # Convert numeric ID to topic name
        topic_index = int(topic_identifier) - 1  # Convert to 0-based index
        
        # Get the topic name by index
        topics_sql = text("""
            SELECT unnest(topics) as topic, COUNT(*) as count
            FROM articles 
            WHERE topics IS NOT NULL 
            AND sentiment_score IS NOT NULL
            GROUP BY unnest(topics)
            ORDER BY count DESC
            LIMIT 50
        """)
        
        topics_result = (await db.execute(topics_sql)).mappings().all()
        
        if 0 <= topic_index < len(topics_result):
            topic_name = topics_result[topic_index]['topic']
        else:
            # Invalid index, return empty with helpful message
            return {
                "error": f"Invalid topic index {topic_identifier}. Available topics: 1-{len(topics_result)}",
                "available_topics": [{"index": i+1, "topic": r['topic'], "count": r['count']} for i, r in enumerate(topics_result[:10])]
            }
    
    sql = text("""
        SELECT 
            DATE(published_at) as period,
            COUNT(*) as total_articles,
            AVG(sentiment_score) as avg_sentiment,
            COUNT(*) FILTER (WHERE sentiment_score > 0.1) as positive_count,
            COUNT(*) FILTER (WHERE sentiment_score BETWEEN -0.1 AND 0.1) as neutral_count,
            COUNT(*) FILTER (WHERE sentiment_score < -0.1) as negative_count
        FROM articles
        WHERE topics && ARRAY[:topic_name]
          AND published_at >= :since_dt
          AND sentiment_score IS NOT NULL
        GROUP BY DATE(published_at)
        ORDER BY period DESC
        LIMIT 1000
    """)
    params = {"topic_name": topic_name, "since_dt": since_dt}
    rows = (await db.execute(sql, params)).mappings().all()
    
    # Add metadata about the topic
    result = [dict(r) for r in rows]
    if result:
        result.insert(0, {
            "metadata": {
                "topic": topic_name,
                "query": topic_identifier,
                "days": days,
                "total_periods": len(result) - 1  # Subtract 1 for metadata
            }
        })
    elif not rows:
        # No data found, provide helpful response
        return {
            "topic": topic_name,
            "query": topic_identifier,
            "days": days,
            "message": f"No sentiment data found for topic '{topic_name}' in the last {days} days",
            "data": []
        }
    
    return result

@router.get("/source/{domain}")
async def sentiment_source(
    domain: str = Path(..., description="domaine ex: www.bbc.com"),
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_session),
):
    domain = domain.strip().lower()  # normalisation simple
    since_dt = datetime.utcnow() - timedelta(days=days)
    
    sql = text("""
        SELECT 
            DATE(published_at) as period,
            domain,
            COUNT(*) as total_articles,
            AVG(sentiment_score) as avg_sentiment,
            COUNT(*) FILTER (WHERE sentiment_score > 0.1) as positive_count,
            COUNT(*) FILTER (WHERE sentiment_score BETWEEN -0.1 AND 0.1) as neutral_count,
            COUNT(*) FILTER (WHERE sentiment_score < -0.1) as negative_count
        FROM articles
        WHERE domain ILIKE :domain
          AND published_at >= :since_dt
          AND sentiment_score IS NOT NULL
        GROUP BY DATE(published_at), domain
        ORDER BY period DESC
        LIMIT 1000
    """)
    params = {"domain": f"%{domain}%", "since_dt": since_dt}
    rows = (await db.execute(sql, params)).mappings().all()
    return [dict(r) for r in rows]