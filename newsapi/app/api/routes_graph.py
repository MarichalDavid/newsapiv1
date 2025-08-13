
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core.db import get_session

router = APIRouter(prefix="/graph", tags=["graph"])

@router.get("/cluster/{cluster_id}")
async def graph_cluster(cluster_id: str, db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(text("SELECT id, title, domain FROM articles WHERE cluster_id = :cid"), {"cid": cluster_id})).mappings().all()
    nodes = [{"id": f"a{r['id']}", "label": r["title"], "type":"article"} for r in rows]
    edges = [{"source": f"a{r['id']}", "target": r["domain"], "type":"covers"} for r in rows]
    for r in rows:
        nodes.append({"id": r["domain"], "label": r["domain"], "type":"source"})
    # Dedup nodes by id
    uniq = {n["id"]: n for n in nodes}
    return {"nodes": list(uniq.values()), "edges": edges}
