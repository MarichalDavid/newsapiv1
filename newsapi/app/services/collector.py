# app/services/collector.py - Corrections timezone

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import aiohttp
import feedparser
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from ..core.models import Source, Article
from ..core.db import get_session
from .dedupe import content_hash
from .sitemap import discover_from_sitemap

logger = logging.getLogger(__name__)

class CollectorService:
    """Service principal de collecte d'articles"""
    
    def __init__(self):
        self.session_timeout = aiohttp.ClientTimeout(total=30)
        self.max_articles_per_source = 50
    
    def normalize_datetime(self, dt: Optional[datetime]) -> Optional[datetime]:
        """✅ NOUVELLE FONCTION: Normalise les datetime pour PostgreSQL"""
        if dt is None:
            return None
        
        # Si le datetime a un timezone, le convertir en UTC puis retirer le timezone
        if dt.tzinfo is not None:
            # Convertir en UTC
            dt_utc = dt.astimezone(timezone.utc)
            # Retirer le timezone info pour PostgreSQL TIMESTAMP WITHOUT TIME ZONE
            return dt_utc.replace(tzinfo=None)
        
        # Si pas de timezone, on assume que c'est déjà en UTC
        return dt
        
    async def fetch_feed_content(self, session: aiohttp.ClientSession, url: str) -> str:
        """Récupère le contenu d'un feed RSS/XML"""
        try:
            async with session.get(url, timeout=self.session_timeout) as response:
                if response.status == 200:
                    content = await response.text()
                    return content
                else:
                    logger.warning(f"HTTP {response.status} for {url}")
                    return ""
        except Exception as e:
            logger.error(f"Fetch error for {url}: {e}")
            return ""
    
    def parse_rss_feed(self, content: str, source_url: str) -> List[Dict[str, Any]]:
        """Parse un feed RSS de manière robuste"""
        try:
            if not content or len(content.strip()) < 50:
                logger.warning(f"Content too short for {source_url}")
                return []
            
            feed = feedparser.parse(content)
            
            if hasattr(feed, 'bozo') and feed.bozo:
                logger.warning(f"RSS parsing warning for {source_url}: {feed.bozo_exception}")
            
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                logger.warning(f"No entries found in RSS feed for {source_url}")
                return []
            
            articles = []
            for entry in feed.entries[:self.max_articles_per_source]:
                try:
                    title = getattr(entry, 'title', 'No title').strip()
                    link = getattr(entry, 'link', '').strip()
                    summary = getattr(entry, 'summary', '').strip()
                    
                    if not title or not link:
                        continue
                    
                    article_data = {
                        "title": title,
                        "url": link,
                        "description": summary,
                        "published_at": self.parse_date(getattr(entry, 'published', None)),
                        "author": getattr(entry, 'author', None),
                    }
                    
                    articles.append(article_data)
                    
                except Exception as e:
                    logger.error(f"Error parsing RSS entry: {e}")
                    continue
            
            logger.info(f"Parsed {len(articles)} articles from RSS for {source_url}")
            return articles
            
        except Exception as e:
            logger.error(f"RSS parsing failed for {source_url}: {e}")
            return []
    
    def parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """✅ CORRIGÉ: Parse une date et normalise le timezone"""
        if not date_str:
            return self.normalize_datetime(datetime.now(timezone.utc))
        
        try:
            from email.utils import parsedate_to_datetime
            parsed_dt = parsedate_to_datetime(date_str)
            return self.normalize_datetime(parsed_dt)
        except:
            try:
                from dateutil.parser import parse
                parsed_dt = parse(date_str)
                return self.normalize_datetime(parsed_dt)
            except:
                return self.normalize_datetime(datetime.now(timezone.utc))
    
    def generate_content_hash(self, title: str, url: str) -> str:
        """Génère un hash unique pour le contenu"""
        content = f"{title}|{url}"
        return content_hash(content)
    
    def normalize_url(self, url: str) -> str:
        """Normalise une URL"""
        try:
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        except:
            return url
    
    async def save_articles(self, db: AsyncSession, source: Source, articles: List[Dict[str, Any]]) -> int:
        """✅ CORRIGÉ: Sauvegarde les articles avec datetime normalisés"""
        saved_count = 0
        
        for article_data in articles:
            try:
                url = article_data["url"]
                canonical_url = self.normalize_url(url)
                domain = urlparse(url).netloc
                content_hash = self.generate_content_hash(article_data["title"], canonical_url)
                
                # ✅ CORRECTION: Normaliser les datetime
                published_at = self.normalize_datetime(article_data.get("published_at"))
                fetched_at = self.normalize_datetime(datetime.now(timezone.utc))
                
                # Créer l'objet Article
                article = Article(
                    source_id=source.id,
                    url=url,
                    canonical_url=canonical_url,
                    domain=domain,
                    title=article_data["title"],
                    summary_feed=article_data.get("description"),
                    published_at=published_at,  # ✅ Datetime normalisé
                    authors=[article_data["author"]] if article_data.get("author") else None,
                    content_hash=content_hash,
                    fetched_at=fetched_at,  # ✅ Datetime normalisé
                    status="new"
                )
                
                # UPSERT avec PostgreSQL
                stmt = insert(Article).values(
                    source_id=article.source_id,
                    url=article.url,
                    canonical_url=article.canonical_url,
                    domain=article.domain,
                    title=article.title,
                    summary_feed=article.summary_feed,
                    published_at=article.published_at,
                    authors=article.authors,
                    content_hash=article.content_hash,
                    fetched_at=article.fetched_at,
                    status=article.status
                )
                
                stmt = stmt.on_conflict_do_update(
                    index_elements=['canonical_url'],
                    set_={
                        'fetched_at': stmt.excluded.fetched_at,
                        'status': stmt.excluded.status
                    }
                )
                
                await db.execute(stmt)
                saved_count += 1
                
            except Exception as e:
                logger.error(f"Error saving article {article_data.get('title', 'Unknown')}: {e}")
                continue
        
        try:
            await db.commit()
            logger.info(f"Saved {saved_count} articles for source {source.name}")
        except Exception as e:
            await db.rollback()
            logger.error(f"Error committing articles for source {source.name}: {e}")
            return 0
        
        return saved_count
    
    async def process_source(self, db: AsyncSession, source: Source) -> Dict[str, Any]:
        """Traite une source individuelle"""
        try:
            logger.info(f"Processing source {source.id}: {source.site_domain}")
            
            async with aiohttp.ClientSession() as session:
                content = await self.fetch_feed_content(session, source.feed_url)
                
                if not content:
                    logger.warning(f"No content retrieved for {source.feed_url}")
                    # Fallback: try sitemap discovery
                    return await self.process_source_via_sitemap(db, source)
                
                articles_data = self.parse_rss_feed(content, source.feed_url)
                
                if not articles_data:
                    logger.warning(f"No articles parsed for {source.feed_url}")
                    # Fallback: try sitemap discovery
                    return await self.process_source_via_sitemap(db, source)
                
                saved_count = await self.save_articles(db, source, articles_data)
                
                logger.info(f"Source {source.name}: {saved_count} articles saved")
                return {"success": 1, "failed": 0, "articles": saved_count}
                
        except Exception as e:
            logger.error(f"Error processing source {source.id}: {e}")
            return {"success": 0, "failed": 1, "articles": 0}

# Instances et fonctions globales
collector_service = CollectorService()

async def run_collection_once(db: AsyncSession) -> Dict[str, Any]:
    """Exécute un cycle de collecte complet"""
    try:
        logger.info("[collector] Starting collection cycle")
        
        stmt = select(Source).where(Source.active == True)
        result = await db.execute(stmt)
        sources = result.scalars().all()
        
        if not sources:
            logger.warning("[collector] No active sources found")
            return {"success": 0, "failed": 0, "articles": 0}
        
        logger.info(f"[collector] active sources: {len(sources)}")
        
        total_success = 0
        total_failed = 0
        total_articles = 0
        
        for source in sources:
            try:
                result = await collector_service.process_source(db, source)
                total_success += result["success"]
                total_failed += result["failed"]
                total_articles += result["articles"]
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"[collector] Error processing source {source.id}: {e}")
                total_failed += 1
        
        logger.info(f"[collector] Collection completed: {total_success} success, {total_failed} failed, {total_articles} articles total")
        
        return {
            "success": total_success,
            "failed": total_failed,
            "articles": total_articles,
            "timestamp": datetime.now(timezone.utc)  # ✅ CORRIGÉ: Avec timezone UTC
        }
        
    except Exception as e:
        logger.error(f"[collector] Collection cycle failed: {e}")
        return {"success": 0, "failed": 1, "articles": 0, "error": str(e)}
    
    async def process_source_via_sitemap(self, db: AsyncSession, source: Source) -> Dict[str, Any]:
        """Fallback: découverte d'articles via sitemap"""
        try:
            logger.info(f"Trying sitemap discovery for {source.site_domain}")
            
            # Discover URLs from sitemap
            sitemap_urls = discover_from_sitemap(source.site_domain, limit=20)
            
            if not sitemap_urls:
                logger.warning(f"No URLs found in sitemap for {source.site_domain}")
                return {"success": 0, "failed": 1, "articles": 0}
            
            # Convert sitemap URLs to article data format
            articles_data = []
            for url_info in sitemap_urls:
                url = url_info.get("url", "")
                if url:
                    # Extract title from URL path as fallback
                    path_parts = url.rstrip('/').split('/')
                    title = path_parts[-1].replace('-', ' ').replace('_', ' ').title() if path_parts else "Article"
                    
                    articles_data.append({
                        'title': title,
                        'url': url,
                        'canonical_url': url,
                        'summary_feed': f"Article discovered from sitemap: {source.site_domain}",
                        'published_at': self.parse_date(None),  # Current time as fallback
                        'authors': None,
                        'full_text': None,
                        'lang': None
                    })
            
            if articles_data:
                saved_count = await self.save_articles(db, source, articles_data)
                logger.info(f"Sitemap discovery for {source.name}: {saved_count} articles saved")
                return {"success": 1, "failed": 0, "articles": saved_count, "method": "sitemap"}
            else:
                return {"success": 0, "failed": 1, "articles": 0}
                
        except Exception as e:
            logger.error(f"Sitemap discovery failed for {source.site_domain}: {e}")
            return {"success": 0, "failed": 1, "articles": 0, "error": str(e)}

async def get_collection_health() -> Dict[str, Any]:
    """Vérifie la santé de la collecte"""
    try:
        async for db in get_session():
            result = await db.execute(text("""
                SELECT 
                    COUNT(*) as total_articles,
                    COUNT(*) FILTER (WHERE fetched_at >= NOW() - INTERVAL '24 hours') as articles_24h,
                    COUNT(*) FILTER (WHERE fetched_at >= NOW() - INTERVAL '1 hour') as articles_1h,
                    MAX(fetched_at) as last_fetch
                FROM articles
            """))
            
            stats = result.fetchone()
            
            if stats[1] > 0:
                status = "active"
            elif stats[0] > 0:
                status = "inactive"
            else:
                status = "empty"
            
            return {
                "status": status,
                "total_articles": stats[0],
                "articles_24h": stats[1],
                "articles_1h": stats[2],
                "last_fetch": stats[3],
                "timestamp": datetime.now(timezone.utc)  # ✅ CORRIGÉ
            }
            
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc)  # ✅ CORRIGÉ
        }