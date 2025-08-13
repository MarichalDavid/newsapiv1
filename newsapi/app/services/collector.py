from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from ..core.models import Source, Article
from ..services.discovery import fetch_feed, parse_feed
from ..services.sitemap import discover_from_sitemap
from ..services.enrichment import enrich_html
from ..services.normalize import guess_lang
from ..services.dedupe import content_hash
from ..services.summarize import choose_summary
from ..services.nlp_keywords import extract_keywords
from ..services.nlp_entities import extract_entities
from ..utils.url import canonical_url
from urllib.parse import urlparse
from datetime import datetime
from simhash import Simhash
import traceback
from ..services.normalize import to_utc_naive

def simhash_int63(text: str) -> int:
    from simhash import Simhash
    v = Simhash(text).value           # 64-bit non signé
    return v & ((1 << 63) - 1)        # clamp en [0 .. 2^63-1]


async def run_collection_once(db: AsyncSession):
    res = await db.execute(
        select(
            Source.id, Source.feed_url, Source.site_domain,
            Source.etag, Source.last_modified, Source.enrichment
        ).where(Source.active == True)
    )
    sources = [dict(r) for r in res.mappings().all()]
    print(f"[collector] active sources: {len(sources)}", flush=True)

    for s in sources:
        try:
            status, r = fetch_feed(s["feed_url"], s["etag"], s["last_modified"])
            items = []
            if status != 304 and status < 400:
                et = r.headers.get("ETag"); lm = r.headers.get("Last-Modified")
                if et or lm:
                    await db.execute(
                        update(Source).where(Source.id==s["id"]).values(
                            etag=et, last_modified=lm, updated_at=datetime.utcnow()
                        )
                    )
                items = list(parse_feed(r.content))
            if not items:
                sm = discover_from_sitemap(s["site_domain"], limit=20)
                for u in sm:
                    items.append({"title": None, "link": u["url"], "summary": None,
                                  "published": None, "authors": None, "raw": None})
            print(f"[collector] {s['site_domain']} items={len(items)}", flush=True)

            for item in items[:20]:  # limiter pour le premier run
                try:
                    url = canonical_url(item.get("link"))
                    if not url:
                        continue
                    domain = urlparse(url).netloc
                    published_at = to_utc_naive(item.get("published"))
                    title = item.get("title") or "(untitled)"
                    summary_feed = item.get("summary")
                    authors = item.get("authors")

                    full_text = None
                    if s["enrichment"] == "html":
                        try:
                            enr = enrich_html(url)
                            full_text = enr.get("full_text")
                        except Exception:
                            full_text = None

                    summary_final, summary_source, summary_llm = choose_summary(summary_feed, full_text)
                    lang = guess_lang(full_text or summary_final or title) or None
                    kws = extract_keywords(full_text or summary_final or title, lang=lang or "en") or []

                    topics = []
                    for k in kws:
                        kl = k.lower()
                        if any(x in kl for x in ["bank","banque","financ","bourse","crypto"]): topics.append("economie")
                        if any(x in kl for x in ["politic","diplom","election","parlement"]): topics.append("politique")
                        if any(x in kl for x in ["ai","intelligence artificielle","machine learning","ml"]): topics.append("tech")
                        if any(x in kl for x in ["sport","match","league"]): topics.append("sport")
                    topics = list(dict.fromkeys(topics)) or None

                    text_for_hash = full_text or (title + (summary_feed or ""))
                    h = content_hash(text_for_hash)
                    sh = simhash_int63(full_text or title or "")
                    cluster_id = hex(sh)[2:6]

                    # Utiliser INSERT ... ON CONFLICT DO NOTHING pour gérer les doublons
                    stmt = insert(Article).values(
                        source_id=s["id"],
                        url=url, canonical_url=url, domain=domain,
                        title=title, summary_feed=summary_feed, published_at=published_at,
                        authors=authors, full_text=full_text, jsonld=None, lang=lang,
                        keywords=kws, entities=extract_entities(full_text or summary_final or "", lang=lang or "en"),
                        summary_llm=summary_llm, summary_final=summary_final, summary_source=summary_source,
                        topics=topics, content_hash=h, simhash=sh, cluster_id=cluster_id,
                        status="processed", raw=item.get("raw")
                    )
                    stmt = stmt.on_conflict_do_nothing(index_elements=['canonical_url'])
                    result = await db.execute(stmt)
                    
                    # Log si l'article a été inséré ou ignoré
                    if result.rowcount == 0:
                        print(f"[collector] duplicate URL ignored: {url}", flush=True)
                    else:
                        print(f"[collector] article inserted: {url}", flush=True)
                    
                    # IMPORTANT: NE PAS utiliser db.add() ici !
                    # L'insertion se fait directement avec stmt ci-dessus
                    
                except Exception as e:
                    print(f"[collector] insert fail {s['site_domain']} -> {e}", flush=True)
                    traceback.print_exc()
                    # Ne pas faire de rollback ici, continuer avec les autres articles
                    continue

            await db.commit()
        except Exception as e:
            print(f"[collector] source fail {s['site_domain']} -> {e}", flush=True)
            traceback.print_exc()
            try: 
                await db.rollback()
            except: 
                pass