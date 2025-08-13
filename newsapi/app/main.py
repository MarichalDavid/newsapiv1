from fastapi import FastAPI
from .core.db import get_session
from .core.models import Source
from .api.routes_sources import router as sources_router
from .api.routes_articles import router as articles_router
from .api.routes_summaries import router as summaries_router
from .api.routes_topics import router as topics_router
from .api.routes_clusters import router as clusters_router
from .api.routes_exports import router as exports_router
from fastapi.middleware.cors import CORSMiddleware
from .middleware_cache import RedisGetCacheMiddleware
from .api.routes_synthesis import router as synthesis_router
from .api.routes_search import router as search_router
from .api.routes_sentiment import router as sentiment_router
from .api.routes_graph import router as graph_router
from .api.routes_relations import router as relations_router

app = FastAPI(title="NewsIA API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(sources_router, prefix="/api/v1")
app.include_router(articles_router, prefix="/api/v1")
app.include_router(summaries_router, prefix="/api/v1")
app.include_router(topics_router, prefix="/api/v1")
app.include_router(clusters_router, prefix="/api/v1")
app.include_router(exports_router, prefix="/api/v1")
app.include_router(synthesis_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(sentiment_router, prefix="/api/v1")
app.include_router(graph_router, prefix="/api/v1")
app.include_router(relations_router, prefix="/api/v1")



@app.get("/health")
def health():
    return {"status":"ok"}


from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
from sqlalchemy import text
import os, json

REQS = Counter("newsia_requests_total", "Total API requests", ["path"])

@app.on_event("startup")
async def _bootstrap():
    # Import feeds from config if no sources
    try:
        async for db in get_session():
            res = await db.execute(text("SELECT COUNT(*) FROM sources"))
            n = res.scalar_one()
            if n == 0:
                path = os.getenv("FEEDS_FILE", "/app/config/rss_feeds_global.json")
                if os.path.exists(path):
                    data = json.load(open(path,"r",encoding="utf-8"))
                    from urllib.parse import urlparse
                    from sqlalchemy import insert
                    for it in data:
                        u = it.get("url"); name = it.get("name") or urlparse(u).netloc
                        dom = urlparse(u).netloc
                        await db.execute(insert(Source).values(name=name, feed_url=u, site_domain=dom, method="rss", enrichment="html", active=True))
                    await db.commit()
    except Exception as e:
        print("bootstrap error:", e, flush=True)

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
