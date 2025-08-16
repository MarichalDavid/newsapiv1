"""
Simple topic extraction and clustering service using LLM
"""
import logging
import hashlib
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, update
from ..core.models import Article
from .llm import generate_llm

logger = logging.getLogger(__name__)

async def extract_topics_from_text(text: str, max_topics: int = 3) -> List[str]:
    """Extract topics from text using LLM"""
    if not text or len(text.strip()) < 20:
        return []
    
    prompt = f"""Extract {max_topics} main topics from this news text. Return only topic keywords separated by commas, no explanations.

Examples:
- "technology, artificial intelligence, innovation"
- "politics, election, democracy"
- "economy, finance, market"

Text: {text[:1000]}

Topics:"""
    
    try:
        result = await generate_llm(prompt, max_tokens=50, temperature=0.1)
        if not result or result.startswith("Error:"):
            return []
        
        # Parse topics from result
        topics = []
        for topic in result.split(','):
            topic = topic.strip().lower()
            if topic and len(topic) > 2 and len(topic) < 30:
                topics.append(topic)
        
        return topics[:max_topics]
    except Exception as e:
        logger.error(f"Topic extraction error: {e}")
        return []

def generate_cluster_id(title: str, domain: str) -> str:
    """Generate a simple cluster ID based on content similarity"""
    # Simple clustering based on domain + first 3 words of title
    words = title.lower().split()[:3]
    cluster_key = f"{domain}_{' '.join(words)}"
    return hashlib.md5(cluster_key.encode()).hexdigest()[:8]

async def process_articles_for_topics_and_clusters(
    session: AsyncSession, 
    limit: int = 50,
    since_hours: int = 24
) -> Dict[str, int]:
    """Process recent articles to extract topics and assign clusters"""
    
    # Get articles without topics or clusters
    sql = text("""
        SELECT id, title, summary_final, domain, published_at
        FROM articles 
        WHERE published_at >= NOW() - INTERVAL '%s hours'
        AND (topics IS NULL OR array_length(topics, 1) = 0 OR cluster_id IS NULL)
        ORDER BY published_at DESC
        LIMIT %s
    """ % (since_hours, limit))
    
    result = await session.execute(sql)
    articles = result.mappings().all()
    
    if not articles:
        return {"processed": 0, "topics_extracted": 0, "clusters_assigned": 0}
    
    topics_count = 0
    clusters_count = 0
    
    for article in articles:
        article_id = article['id']
        title = article['title'] or ""
        summary = article['summary_final'] or ""
        domain = article['domain'] or ""
        
        # Extract topics
        content = f"{title}. {summary}"
        topics = await extract_topics_from_text(content)
        
        # Generate cluster ID
        cluster_id = generate_cluster_id(title, domain)
        
        # Update article with topics and cluster
        update_sql = text("""
            UPDATE articles 
            SET topics = :topics, cluster_id = :cluster_id
            WHERE id = :article_id
        """)
        
        await session.execute(update_sql, {
            "topics": topics if topics else None,
            "cluster_id": cluster_id,
            "article_id": article_id
        })
        
        if topics:
            topics_count += 1
        if cluster_id:
            clusters_count += 1
    
    await session.commit()
    
    return {
        "processed": len(articles),
        "topics_extracted": topics_count,
        "clusters_assigned": clusters_count
    }

async def process_basic_topics_fallback(session: AsyncSession, limit: int = 100) -> int:
    """Fallback: Extract basic topics from keywords or domain-based classification"""
    
    # Simple domain-based topic assignment
    domain_topics = {
        'bbc.co.uk': ['news', 'international', 'media'],
        'cnn.com': ['news', 'politics', 'breaking'],
        'nytimes.com': ['news', 'journalism', 'politics'],
        'sciencedaily.com': ['science', 'research', 'technology'],
        'techcrunch.com': ['technology', 'startups', 'innovation'],
        'reuters.com': ['news', 'business', 'international'],
        'bloomberg.com': ['finance', 'business', 'economy'],
        'cointelegraph.com': ['cryptocurrency', 'blockchain', 'finance']
    }
    
    # Update articles without topics using domain mapping
    sql = text("""
        SELECT id, domain, title
        FROM articles 
        WHERE topics IS NULL OR array_length(topics, 1) = 0
        ORDER BY published_at DESC
        LIMIT :limit
    """)
    
    result = await session.execute(sql, {"limit": limit})
    articles = result.mappings().all()
    
    updated_count = 0
    
    for article in articles:
        domain = article['domain'] or ""
        title = article['title'] or ""
        
        # Get topics from domain mapping
        topics = []
        for d, t in domain_topics.items():
            if d in domain:
                topics = t
                break
        
        # Add title-based topics
        title_lower = title.lower()
        if 'technology' in title_lower or 'tech' in title_lower:
            topics.append('technology')
        if 'politics' in title_lower or 'election' in title_lower:
            topics.append('politics')
        if 'economy' in title_lower or 'economic' in title_lower:
            topics.append('economy')
        if 'science' in title_lower or 'research' in title_lower:
            topics.append('science')
        if 'crypto' in title_lower or 'bitcoin' in title_lower:
            topics.append('cryptocurrency')
        
        # Remove duplicates and limit
        topics = list(set(topics))[:3]
        
        if topics:
            update_sql = text("""
                UPDATE articles 
                SET topics = :topics
                WHERE id = :article_id
            """)
            
            await session.execute(update_sql, {
                "topics": topics,
                "article_id": article['id']
            })
            updated_count += 1
    
    await session.commit()
    return updated_count