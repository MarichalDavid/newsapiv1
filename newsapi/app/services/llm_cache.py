import hashlib, json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from ..core.models import LlmCache

def make_cache_key(model: str, payload: dict) -> str:
    raw = json.dumps({"model": model, "payload": payload}, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

async def get_cached(db: AsyncSession, key: str):
    res = await db.execute(select(LlmCache).where(LlmCache.cache_key == key))
    row = res.scalar_one_or_none()
    return row.response if row else None

async def put_cache(db: AsyncSession, key: str, model: str, params: dict, response: str):
    await db.execute(insert(LlmCache).values(cache_key=key, model=model, params=params, response=response))
    await db.commit()
