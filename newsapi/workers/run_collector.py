import asyncio
from app.core.db import get_session
from app.services.collector import run_collection_once
from sqlalchemy import text
from app.services.topics_bertopic import build_and_assign as build_topics
from app.services.sentiment_simple import label_text
from app.services.facts import extract_facts

async def _aggregate_sentiment(session):
    await session.execute(text("""
        INSERT INTO source_sentiment_daily(d, domain, pos_count, neu_count, neg_count)
        SELECT current_date, domain,
            SUM((COALESCE(sentiment_label,'neu')='pos')::int),
            SUM((COALESCE(sentiment_label,'neu')='neu')::int),
            SUM((COALESCE(sentiment_label,'neu')='neg')::int)
        FROM articles
        WHERE published_at >= current_date
        GROUP BY domain
        ON CONFLICT (d, domain) DO UPDATE SET
            pos_count=EXCLUDED.pos_count, neu_count=EXCLUDED.neu_count, neg_count=EXCLUDED.neg_count
    """))
    await session.commit()

async def _refresh_mv(session):
    try:
        await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_topics_daily"))
        await session.commit()
    except Exception:
        await session.execute(text("REFRESH MATERIALIZED VIEW mv_topics_daily"))
        await session.commit()

from app.core.config import settings

async def main():
    topics_refresh_counter = 0
    mv_refresh_counter = 0
    agg_counter = 0
    while True:
        async for session in get_session():
            try:
                await run_collection_once(session)
            except Exception as e:
                print("Collector error:", e, flush=True)
                topics_refresh_counter += 1
        mv_refresh_counter += 1
        agg_counter += 1
        if topics_refresh_counter >= max(1, (6*60)//settings.DEFAULT_FREQ_MIN):
            try:
                async for s in get_session():
                    await build_topics(s)
            except Exception as e:
                print('topics error:', e)
            topics_refresh_counter = 0
        if mv_refresh_counter >= max(1, (30)//settings.DEFAULT_FREQ_MIN):
            try:
                async for s in get_session():
                    await _refresh_mv(s)
            except Exception as e:
                print('mv refresh error:', e)
            mv_refresh_counter = 0
        if agg_counter >= max(1, (10)//settings.DEFAULT_FREQ_MIN):
            try:
                async for s in get_session():
                    await _aggregate_sentiment(s)
            except Exception as e:
                print('agg error:', e)
            agg_counter = 0
        await asyncio.sleep(settings.DEFAULT_FREQ_MIN * 60)

if __name__ == "__main__":
    asyncio.run(main())
