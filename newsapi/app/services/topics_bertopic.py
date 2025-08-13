
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer

async def build_and_assign(session: AsyncSession):
    q = await session.execute(text("""
        SELECT id, COALESCE(summary_final,title) AS text
        FROM articles
        WHERE published_at >= now() - interval '7 days'
        ORDER BY published_at DESC
        LIMIT 1000
    """))
    rows = q.mappings().all()
    if not rows:
        return
    docs = [r["text"] or "" for r in rows]
    ids = [r["id"] for r in rows]
    embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    model = BERTopic(embedding_model=embedder, verbose=False)
    topics, _ = model.fit_transform(docs)
    for aid, t in zip(ids, topics):
        await session.execute(text("""
            UPDATE articles SET topic_id=:t, topic_label=:l, topic_score=:s WHERE id=:id
        """), {"t": int(t) if t is not None else -1, "l": f"Topic {t}", "s": 0.5, "id": aid})
    await session.commit()
