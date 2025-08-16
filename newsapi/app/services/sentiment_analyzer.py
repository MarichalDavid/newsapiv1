"""
Sentiment analysis service using LLM
"""
import logging
import re
from typing import Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, update
from ..core.models import Article
from .llm import generate_llm

logger = logging.getLogger(__name__)

def analyze_sentiment_simple(text: str) -> Tuple[float, str, float]:
    """Simple rule-based sentiment analysis as fallback"""
    if not text:
        return 0.0, "neutral", 0.5
    
    text_lower = text.lower()
    
    # Positive words
    positive_words = [
        'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 
        'success', 'win', 'victory', 'breakthrough', 'progress', 'improvement',
        'benefit', 'positive', 'gain', 'growth', 'increase', 'rising', 'up'
    ]
    
    # Negative words  
    negative_words = [
        'bad', 'terrible', 'awful', 'horrible', 'disaster', 'crisis',
        'failure', 'lose', 'loss', 'defeat', 'decline', 'decrease', 'drop',
        'problem', 'issue', 'negative', 'concern', 'worry', 'fear', 'down'
    ]
    
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    
    total_words = len(text_lower.split())
    if total_words == 0:
        return 0.0, "neutral", 0.5
    
    # Calculate sentiment score (-1 to 1)
    sentiment_score = (positive_count - negative_count) / max(total_words / 10, 1)
    sentiment_score = max(-1.0, min(1.0, sentiment_score))
    
    # Determine label
    if sentiment_score > 0.1:
        label = "positive"
        confidence = min(0.9, 0.5 + abs(sentiment_score))
    elif sentiment_score < -0.1:
        label = "negative"
        confidence = min(0.9, 0.5 + abs(sentiment_score))
    else:
        label = "neutral"
        confidence = 0.6
    
    return sentiment_score, label, confidence

async def analyze_sentiment_llm(text: str) -> Tuple[float, str, float]:
    """Analyze sentiment using LLM"""
    if not text or len(text.strip()) < 10:
        return analyze_sentiment_simple(text)
    
    prompt = f"""Analyze the sentiment of this news text. Respond with only:
SENTIMENT: [positive/negative/neutral]
SCORE: [number from -1.0 to 1.0]
CONFIDENCE: [number from 0.0 to 1.0]

Examples:
- Good news: SENTIMENT: positive, SCORE: 0.7, CONFIDENCE: 0.8
- Bad news: SENTIMENT: negative, SCORE: -0.6, CONFIDENCE: 0.9  
- Neutral news: SENTIMENT: neutral, SCORE: 0.0, CONFIDENCE: 0.7

Text: {text[:800]}

Response:"""
    
    try:
        result = await generate_llm(prompt, max_tokens=50, temperature=0.1)
        if not result or result.startswith("Error:"):
            return analyze_sentiment_simple(text)
        
        # Parse LLM response
        sentiment_match = re.search(r'SENTIMENT:\s*(\w+)', result, re.IGNORECASE)
        score_match = re.search(r'SCORE:\s*([-\d.]+)', result)
        confidence_match = re.search(r'CONFIDENCE:\s*([\d.]+)', result)
        
        if sentiment_match and score_match and confidence_match:
            sentiment = sentiment_match.group(1).lower()
            score = float(score_match.group(1))
            confidence = float(confidence_match.group(1))
            
            # Validate and clamp values
            score = max(-1.0, min(1.0, score))
            confidence = max(0.0, min(1.0, confidence))
            
            if sentiment not in ['positive', 'negative', 'neutral']:
                return analyze_sentiment_simple(text)
                
            return score, sentiment, confidence
        else:
            return analyze_sentiment_simple(text)
            
    except Exception as e:
        logger.error(f"LLM sentiment analysis error: {e}")
        return analyze_sentiment_simple(text)

async def process_articles_sentiment(
    session: AsyncSession, 
    limit: int = 50,
    since_hours: int = 24,
    use_llm: bool = True
) -> Dict[str, int]:
    """Process recent articles to analyze sentiment"""
    
    # Get articles without sentiment analysis
    sql = text("""
        SELECT id, title, summary_final, published_at
        FROM articles 
        WHERE published_at >= NOW() - INTERVAL '%s hours'
        AND sentiment_score IS NULL
        ORDER BY published_at DESC
        LIMIT %s
    """ % (since_hours, limit))
    
    result = await session.execute(sql)
    articles = result.mappings().all()
    
    if not articles:
        return {"processed": 0, "llm_analyzed": 0, "rule_based": 0}
    
    llm_count = 0
    rule_count = 0
    
    for article in articles:
        article_id = article['id']
        title = article['title'] or ""
        summary = article['summary_final'] or ""
        
        # Combine title and summary for sentiment analysis
        content = f"{title}. {summary}"
        
        # Analyze sentiment
        if use_llm and len(content.strip()) > 20:
            score, label, confidence = await analyze_sentiment_llm(content)
            llm_count += 1
        else:
            score, label, confidence = analyze_sentiment_simple(content)
            rule_count += 1
        
        # Update article with sentiment data
        update_sql = text("""
            UPDATE articles 
            SET sentiment_score = :score, 
                sentiment_label = :label, 
                sentiment_confidence = :confidence
            WHERE id = :article_id
        """)
        
        await session.execute(update_sql, {
            "score": score,
            "label": label,
            "confidence": confidence,
            "article_id": article_id
        })
    
    await session.commit()
    
    return {
        "processed": len(articles),
        "llm_analyzed": llm_count,
        "rule_based": rule_count
    }

async def bulk_sentiment_analysis_fallback(session: AsyncSession, limit: int = 200) -> int:
    """Fallback: Apply rule-based sentiment to all articles without sentiment"""
    
    sql = text("""
        SELECT id, title, summary_final
        FROM articles 
        WHERE sentiment_score IS NULL
        ORDER BY published_at DESC
        LIMIT :limit
    """)
    
    result = await session.execute(sql, {"limit": limit})
    articles = result.mappings().all()
    
    updated_count = 0
    
    for article in articles:
        title = article['title'] or ""
        summary = article['summary_final'] or ""
        content = f"{title}. {summary}"
        
        score, label, confidence = analyze_sentiment_simple(content)
        
        update_sql = text("""
            UPDATE articles 
            SET sentiment_score = :score, 
                sentiment_label = :label, 
                sentiment_confidence = :confidence
            WHERE id = :article_id
        """)
        
        await session.execute(update_sql, {
            "score": score,
            "label": label,
            "confidence": confidence,
            "article_id": article['id']
        })
        updated_count += 1
    
    await session.commit()
    return updated_count