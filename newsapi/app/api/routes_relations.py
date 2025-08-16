
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date as dt_date
from ..core.db import get_session
from ..services.relations_analyzer import analyze_source_relations, get_source_network_stats

router = APIRouter(prefix="/relations", tags=["relations"])

@router.get("/sources")
async def relations_sources(
    date: str = Query(..., description="YYYY-MM-DD"),
    relation: str = Query("co_coverage", description="co_coverage, temporal_correlation, or topic_similarity"),
    min_weight: float = Query(1.0, ge=0.0),
    limit: int = Query(10, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
):
    """Get relationships between news sources for a specific date"""
    try:
        target_date = dt_date.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    relations = await analyze_source_relations(
        session=db,
        target_date=target_date,
        relation_type=relation,
        min_weight=min_weight,
        limit=limit
    )
    
    return relations

@router.get("/network")
async def network_stats(
    date: str = Query(..., description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_session),
):
    """Get network statistics for sources on a specific date"""
    try:
        target_date = dt_date.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")
    
    stats = await get_source_network_stats(session=db, target_date=target_date)
    return stats

@router.get("/sources/{domain}")
async def source_relations(
    domain: str,
    date: str = Query(..., description="YYYY-MM-DD"),
    relation: str = Query("co_coverage"),
    min_weight: float = Query(1.0, ge=0.0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    """Get relationships for a specific source domain"""
    try:
        target_date = dt_date.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    # Get a larger set of relations to ensure we capture the domain
    all_relations = await analyze_source_relations(
        session=db,
        target_date=target_date,
        relation_type=relation,
        min_weight=max(0.1, min_weight / 10),  # Lower threshold to catch more relations
        limit=500  # Get many more to filter
    )
    
    # Filter relations involving the specified domain (partial match)
    domain_relations = [
        rel for rel in all_relations 
        if domain.lower() in rel['src_domain'].lower() or domain.lower() in rel['dst_domain'].lower()
    ]
    
    # If no partial matches, try exact matches with original domains
    if not domain_relations:
        # Check if the domain exists in our data
        check_sql = text("""
            SELECT DISTINCT domain 
            FROM articles 
            WHERE DATE(published_at) = :target_date 
            AND domain ILIKE :domain_pattern
            LIMIT 5
        """)
        
        result = await db.execute(check_sql, {
            "target_date": target_date,
            "domain_pattern": f"%{domain}%"
        })
        matching_domains = [row[0] for row in result.fetchall()]
        
        if matching_domains:
            # Try again with exact domain match
            for exact_domain in matching_domains:
                exact_relations = [
                    rel for rel in all_relations 
                    if rel['src_domain'] == exact_domain or rel['dst_domain'] == exact_domain
                ]
                domain_relations.extend(exact_relations)
    
    # Sort by weight and limit
    domain_relations.sort(key=lambda x: x["weight"], reverse=True)
    return domain_relations[:limit]
