
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core.db import get_session

router = APIRouter(prefix="/search", tags=["search"])

@router.get("/semantic")
async def search_semantic(q: str, k: int = Query(10, le=200), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(text("""
        SELECT id, title, summary_final AS summary, domain, published_at
        FROM articles
        WHERE title ILIKE :q OR summary_final ILIKE :q
        ORDER BY published_at DESC NULLS LAST
        LIMIT :k
    """), {"q": f"%{q}%", "k": k})).mappings().all()
    return [dict(r) for r in rows]
