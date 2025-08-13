
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date as dt_date
from ..core.db import get_session  # adapte l'import si besoin
router = APIRouter(prefix="/relations", tags=["relations"])

@router.get("/sources")
async def relations_sources(
    date: str = Query(..., description="YYYY-MM-DD"),
    relation: str = Query("co_coverage"),
    min_weight: float = Query(1.0, ge=0.0),
    limit: int = Query(10, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
):
    try:
        d = dt_date.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    sql = text("""
        SELECT d, src_domain, dst_domain, relation, weight
        FROM source_relations_daily
        WHERE d = :d AND relation = :relation AND weight >= :w
        ORDER BY weight DESC
        LIMIT :limit
    """)
    rows = (await db.execute(sql, {"d": d, "relation": relation, "w": min_weight, "limit": limit})).mappings().all()
    return [dict(r) for r in rows]
