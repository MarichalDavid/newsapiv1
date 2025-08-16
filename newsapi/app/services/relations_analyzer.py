"""
Relations analysis service for news sources
"""
import logging
from typing import Dict, List, Tuple, Optional
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)

async def analyze_source_relations(
    session: AsyncSession,
    target_date: date,
    relation_type: str = "co_coverage",
    min_weight: float = 1.0,
    limit: int = 100
) -> List[Dict]:
    """Analyze relationships between news sources"""
    
    if relation_type == "co_coverage":
        return await analyze_co_coverage_relations(session, target_date, min_weight, limit)
    elif relation_type == "temporal_correlation":
        return await analyze_temporal_relations(session, target_date, min_weight, limit)
    elif relation_type == "topic_similarity":
        return await analyze_topic_similarity_relations(session, target_date, min_weight, limit)
    else:
        return await analyze_co_coverage_relations(session, target_date, min_weight, limit)

async def analyze_co_coverage_relations(
    session: AsyncSession,
    target_date: date,
    min_weight: float = 1.0,
    limit: int = 100
) -> List[Dict]:
    """Analyze sources that cover similar topics on the same day"""
    
    # Get sources and their topics for the target date
    sql = text("""
        SELECT 
            domain,
            unnest(topics) as topic,
            COUNT(*) as topic_count
        FROM articles 
        WHERE DATE(published_at) = :target_date
        AND topics IS NOT NULL 
        AND array_length(topics, 1) > 0
        GROUP BY domain, unnest(topics)
        HAVING COUNT(*) >= 1
        ORDER BY domain, topic_count DESC
    """)
    
    result = await session.execute(sql, {"target_date": target_date})
    rows = result.mappings().all()
    
    if not rows:
        # Fallback: get sources by article count when no topics
        return await analyze_article_volume_relations(session, target_date, min_weight, limit)
    
    # Build source-topic mapping
    source_topics = defaultdict(set)
    source_article_counts = defaultdict(int)
    
    for row in rows:
        domain = row['domain']
        topic = row['topic']
        count = row['topic_count']
        source_topics[domain].add(topic)
        source_article_counts[domain] += count
    
    # Calculate co-coverage relationships
    relations = []
    sources = list(source_topics.keys())
    
    for i, src1 in enumerate(sources):
        for src2 in sources[i+1:]:
            if src1 != src2:
                topics1 = source_topics[src1]
                topics2 = source_topics[src2]
                
                if topics1 and topics2:
                    # Calculate multiple similarity metrics
                    intersection = len(topics1.intersection(topics2))
                    union = len(topics1.union(topics2))
                    
                    # Jaccard similarity
                    jaccard = intersection / union if union > 0 else 0
                    
                    # Overlap coefficient (for different sized sets)
                    overlap = intersection / min(len(topics1), len(topics2)) if min(len(topics1), len(topics2)) > 0 else 0
                    
                    # Combined weight (favor overlap for better results)
                    weight = max(jaccard * 10, overlap * 5)
                    
                    # Also consider article volume similarity
                    vol1 = source_article_counts[src1]
                    vol2 = source_article_counts[src2]
                    if vol1 > 0 and vol2 > 0:
                        vol_similarity = min(vol1, vol2) / max(vol1, vol2)
                        weight += vol_similarity * 2
                    
                    # Lower threshold for more relationships
                    if weight >= max(0.5, min_weight / 5):
                        relations.append({
                            "d": target_date,
                            "src_domain": src1,
                            "dst_domain": src2,
                            "relation": "co_coverage",
                            "weight": round(weight, 2)
                        })
    
    # If still no relations, use fallback
    if not relations:
        return await analyze_article_volume_relations(session, target_date, min_weight, limit)
    
    # Sort by weight and limit
    relations.sort(key=lambda x: x["weight"], reverse=True)
    return relations[:limit]

async def analyze_article_volume_relations(
    session: AsyncSession,
    target_date: date,
    min_weight: float = 1.0,
    limit: int = 100
) -> List[Dict]:
    """Fallback: Analyze sources by article volume similarity"""
    
    sql = text("""
        SELECT 
            domain,
            COUNT(*) as article_count,
            EXTRACT(HOUR FROM published_at) as avg_hour
        FROM articles 
        WHERE DATE(published_at) = :target_date
        GROUP BY domain, EXTRACT(HOUR FROM published_at)
        HAVING COUNT(*) >= 1
        ORDER BY article_count DESC
    """)
    
    result = await session.execute(sql, {"target_date": target_date})
    rows = result.mappings().all()
    
    if not rows:
        return []
    
    # Group by domain
    source_data = defaultdict(list)
    for row in rows:
        source_data[row['domain']].append({
            'count': row['article_count'],
            'hour': int(row['avg_hour'])
        })
    
    relations = []
    sources = list(source_data.keys())
    
    for i, src1 in enumerate(sources):
        for src2 in sources[i+1:]:
            if src1 != src2:
                # Calculate volume similarity
                vol1 = sum(item['count'] for item in source_data[src1])
                vol2 = sum(item['count'] for item in source_data[src2])
                
                if vol1 > 0 and vol2 > 0:
                    vol_similarity = min(vol1, vol2) / max(vol1, vol2)
                    weight = vol_similarity * 10
                    
                    if weight >= max(1.0, min_weight):
                        relations.append({
                            "d": target_date,
                            "src_domain": src1,
                            "dst_domain": src2,
                            "relation": "co_coverage",
                            "weight": round(weight, 2)
                        })
    
    relations.sort(key=lambda x: x["weight"], reverse=True)
    return relations[:limit]

async def analyze_temporal_relations(
    session: AsyncSession,
    target_date: date,
    min_weight: float = 1.0,
    limit: int = 100
) -> List[Dict]:
    """Analyze sources that publish content at similar times"""
    
    sql = text("""
        SELECT 
            domain,
            EXTRACT(HOUR FROM published_at) as hour,
            COUNT(*) as article_count
        FROM articles 
        WHERE DATE(published_at) = :target_date
        GROUP BY domain, EXTRACT(HOUR FROM published_at)
        HAVING COUNT(*) >= 1
        ORDER BY domain, hour
    """)
    
    result = await session.execute(sql, {"target_date": target_date})
    rows = result.mappings().all()
    
    if not rows:
        return []
    
    # Build source-hour mapping
    source_hours = defaultdict(list)
    source_totals = defaultdict(int)
    
    for row in rows:
        domain = row['domain']
        hour = int(row['hour'])
        count = row['article_count']
        
        source_hours[domain].append({
            'hour': hour,
            'count': count
        })
        source_totals[domain] += count
    
    # Calculate temporal correlations
    relations = []
    sources = list(source_hours.keys())
    
    for i, src1 in enumerate(sources):
        for src2 in sources[i+1:]:
            if src1 != src2:
                hours1 = {h['hour']: h['count'] for h in source_hours[src1]}
                hours2 = {h['hour']: h['count'] for h in source_hours[src2]}
                
                # Calculate different temporal similarity metrics
                common_hours = set(hours1.keys()).intersection(set(hours2.keys()))
                
                weight = 0
                
                if len(common_hours) >= 1:
                    # Basic overlap weight
                    weight += len(common_hours)
                    
                    # Volume correlation in common hours
                    correlation_sum = 0
                    for hour in common_hours:
                        # Normalize by total articles for each source
                        norm1 = hours1[hour] / source_totals[src1] if source_totals[src1] > 0 else 0
                        norm2 = hours2[hour] / source_totals[src2] if source_totals[src2] > 0 else 0
                        correlation_sum += min(norm1, norm2) * 10
                    
                    weight += correlation_sum
                
                # Also consider adjacent hours (sources that publish close in time)
                all_hours1 = set(hours1.keys())
                all_hours2 = set(hours2.keys())
                adjacent_bonus = 0
                
                for h1 in all_hours1:
                    for h2 in all_hours2:
                        if abs(h1 - h2) == 1:  # Adjacent hours
                            adjacent_bonus += 0.5
                
                weight += adjacent_bonus
                
                # Lower threshold for more relationships
                if weight >= max(0.5, min_weight / 2):
                    relations.append({
                        "d": target_date,
                        "src_domain": src1,
                        "dst_domain": src2,
                        "relation": "temporal_correlation",
                        "weight": round(weight, 2)
                    })
    
    # If no relations found, create basic volume-based relationships
    if not relations and len(sources) >= 2:
        for i, src1 in enumerate(sources[:5]):  # Top 5 sources by volume
            for src2 in sources[i+1:6]:  # Top 6 sources
                if src1 != src2:
                    vol1 = source_totals[src1]
                    vol2 = source_totals[src2]
                    if vol1 > 0 and vol2 > 0:
                        # Volume similarity as fallback
                        weight = min(vol1, vol2) / max(vol1, vol2) * 5
                        if weight >= 1.0:
                            relations.append({
                                "d": target_date,
                                "src_domain": src1,
                                "dst_domain": src2,
                                "relation": "temporal_correlation",
                                "weight": round(weight, 2)
                            })
    
    relations.sort(key=lambda x: x["weight"], reverse=True)
    return relations[:limit]

async def analyze_topic_similarity_relations(
    session: AsyncSession,
    target_date: date,
    min_weight: float = 1.0,
    limit: int = 100
) -> List[Dict]:
    """Analyze sources with similar topic distributions"""
    
    sql = text("""
        SELECT 
            domain,
            topics,
            COUNT(*) as article_count
        FROM articles 
        WHERE DATE(published_at) = :target_date
        AND topics IS NOT NULL 
        AND array_length(topics, 1) > 0
        GROUP BY domain, topics
        ORDER BY domain, article_count DESC
    """)
    
    result = await session.execute(sql, {"target_date": target_date})
    rows = result.mappings().all()
    
    if not rows:
        # Fallback to co-coverage analysis
        return await analyze_co_coverage_relations(session, target_date, min_weight, limit)
    
    # Build source topic vectors
    source_vectors = defaultdict(dict)
    source_total_articles = defaultdict(int)
    
    for row in rows:
        domain = row['domain']
        topics = row['topics'] or []
        count = row['article_count']
        source_total_articles[domain] += count
        
        for topic in topics:
            source_vectors[domain][topic] = source_vectors[domain].get(topic, 0) + count
    
    # Calculate multiple similarity metrics between sources
    relations = []
    sources = list(source_vectors.keys())
    
    for i, src1 in enumerate(sources):
        for src2 in sources[i+1:]:
            if src1 != src2:
                vec1 = source_vectors[src1]
                vec2 = source_vectors[src2]
                
                common_topics = set(vec1.keys()).intersection(set(vec2.keys()))
                
                weight = 0
                
                if len(common_topics) >= 1:
                    # Cosine similarity
                    dot_product = sum(vec1[topic] * vec2[topic] for topic in common_topics)
                    norm1 = sum(v**2 for v in vec1.values())**0.5
                    norm2 = sum(v**2 for v in vec2.values())**0.5
                    
                    if norm1 > 0 and norm2 > 0:
                        cosine_sim = dot_product / (norm1 * norm2)
                        weight += cosine_sim * 8
                    
                    # Jaccard similarity on topics
                    all_topics1 = set(vec1.keys())
                    all_topics2 = set(vec2.keys())
                    if all_topics1 and all_topics2:
                        jaccard = len(common_topics) / len(all_topics1.union(all_topics2))
                        weight += jaccard * 5
                    
                    # Volume-weighted overlap
                    total_overlap = sum(min(vec1.get(topic, 0), vec2.get(topic, 0)) for topic in common_topics)
                    max_total = max(source_total_articles[src1], source_total_articles[src2])
                    if max_total > 0:
                        weight += (total_overlap / max_total) * 3
                
                # Lower threshold to ensure we get results
                if weight >= max(0.3, min_weight / 3):
                    relations.append({
                        "d": target_date,
                        "src_domain": src1,
                        "dst_domain": src2,
                        "relation": "topic_similarity",
                        "weight": round(weight, 2)
                    })
    
    # If still no relations, try with even simpler criteria
    if not relations and len(sources) >= 2:
        for i, src1 in enumerate(sources[:5]):
            for src2 in sources[i+1:6]:
                if src1 != src2:
                    # Basic volume similarity as last resort
                    vol1 = source_total_articles[src1]
                    vol2 = source_total_articles[src2]
                    if vol1 > 0 and vol2 > 0:
                        weight = min(vol1, vol2) / max(vol1, vol2) * 3
                        if weight >= 1.0:
                            relations.append({
                                "d": target_date,
                                "src_domain": src1,
                                "dst_domain": src2,
                                "relation": "topic_similarity",
                                "weight": round(weight, 2)
                            })
    
    relations.sort(key=lambda x: x["weight"], reverse=True)
    return relations[:limit]

async def get_source_network_stats(
    session: AsyncSession,
    target_date: date
) -> Dict:
    """Get network statistics for sources on a given date"""
    
    # Get basic source stats
    sql = text("""
        WITH source_stats AS (
            SELECT 
                domain,
                COUNT(*) as article_count
            FROM articles 
            WHERE DATE(published_at) = :target_date
            GROUP BY domain
        ),
        source_topics AS (
            SELECT 
                domain,
                unnest(topics) as topic
            FROM articles 
            WHERE DATE(published_at) = :target_date
            AND topics IS NOT NULL 
            AND array_length(topics, 1) > 0
        )
        SELECT 
            s.domain,
            s.article_count,
            COALESCE(COUNT(DISTINCT st.topic), 0) as unique_topics,
            COALESCE(array_agg(DISTINCT st.topic) FILTER (WHERE st.topic IS NOT NULL), ARRAY[]::text[]) as all_topics
        FROM source_stats s
        LEFT JOIN source_topics st ON s.domain = st.domain
        GROUP BY s.domain, s.article_count
        ORDER BY s.article_count DESC
    """)
    
    result = await session.execute(sql, {"target_date": target_date})
    rows = result.mappings().all()
    
    sources = []
    total_articles = 0
    all_topics = set()
    
    for row in rows:
        domain = row['domain']
        article_count = row['article_count']
        unique_topics = row['unique_topics']
        topics = row['all_topics'] or []
        
        total_articles += article_count
        all_topics.update(topics)
        
        sources.append({
            "domain": domain,
            "article_count": article_count,
            "unique_topics": unique_topics,
            "topics": topics[:10]  # Limit for response size
        })
    
    return {
        "date": target_date,
        "total_sources": len(sources),
        "total_articles": total_articles,
        "total_unique_topics": len(all_topics),
        "sources": sources[:20]  # Limit for response size
    }