# Remplacez le contenu de routes_search.py par ceci

from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, desc
from ..core.db import get_session
from ..core.models import Article
from datetime import datetime, timedelta
import re

router = APIRouter(prefix="/search", tags=["search"])

@router.get("/semantic")
async def search_semantic(
    q: str, 
    k: int = Query(10, le=200), 
    db: AsyncSession = Depends(get_session)
):
    """Recherche sémantique dans les articles"""
    sql = text("""
        SELECT 
            id, 
            title, 
            summary_final AS summary, 
            domain, 
            published_at,
            canonical_url,
            canonical_url AS url  -- ✅ AJOUT du champ url
        FROM articles
        WHERE title ILIKE :q OR summary_final ILIKE :q
        ORDER BY published_at DESC NULLS LAST
        LIMIT :k
    """)
    
    rows = (await db.execute(sql, {"q": f"%{q}%", "k": k})).mappings().all()
    return [dict(r) for r in rows]

@router.get("")
async def search_articles(
    q: str = Query(..., description="Requête de recherche obligatoire"),
    limit: int = Query(20, ge=1, le=100),
    lang: str | None = None,
    db: AsyncSession = Depends(get_session)
):
    """Recherche globale d'articles"""
    conditions = ["title ILIKE :q OR summary_final ILIKE :q"]
    params = {"q": f"%{q}%", "limit": limit}
    
    if lang:
        conditions.append("lang = :lang")
        params["lang"] = lang
    
    where_clause = " AND ".join(conditions)
    
    sql = text(f"""
        SELECT 
            id, 
            title, 
            canonical_url,
            canonical_url AS url,  -- ✅ AJOUT du champ url
            domain, 
            published_at, 
            lang, 
            keywords, 
            topics, 
            summary_final, 
            summary_source
        FROM articles
        WHERE {where_clause}
        ORDER BY published_at DESC NULLS LAST
        LIMIT :limit
    """)
    
    rows = (await db.execute(sql, params)).mappings().all()
    return [dict(r) for r in rows]

@router.get("/entities")
async def search_entities(
    entity_type: str = Query(..., description="Type d'entité: PERSON, ORG, LOCATION, etc."),
    entity_name: str = Query(None, description="Nom de l'entité à rechercher"),
    limit: int = Query(50, ge=1, le=200),
    since_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_session)
):
    """Recherche d'articles par entités nommées"""
    
    since_dt = datetime.utcnow() - timedelta(days=since_days)
    
    if entity_name:
        sql = text("""
            SELECT 
                id, 
                title, 
                canonical_url,
                canonical_url AS url,  -- ✅ AJOUT du champ url
                domain, 
                published_at, 
                lang,
                summary_final, 
                entities
            FROM articles
            WHERE published_at >= :since_dt
              AND (
                title ILIKE :entity_pattern 
                OR summary_final ILIKE :entity_pattern
                OR full_text ILIKE :entity_pattern
              )
            ORDER BY published_at DESC
            LIMIT :limit
        """)
        
        entity_pattern = f"%{entity_name}%"
        params = {"since_dt": since_dt, "entity_pattern": entity_pattern, "limit": limit}
        
    else:
        sql = text("""
            SELECT 
                id, 
                title, 
                canonical_url,
                canonical_url AS url,  -- ✅ AJOUT du champ url
                domain, 
                published_at, 
                lang,
                summary_final, 
                entities
            FROM articles
            WHERE published_at >= :since_dt
              AND entities IS NOT NULL
              AND entities::text ILIKE :entity_type_pattern
            ORDER BY published_at DESC
            LIMIT :limit
        """)
        
        entity_type_pattern = f"%{entity_type}%"
        params = {"since_dt": since_dt, "entity_type_pattern": entity_type_pattern, "limit": limit}
    
    try:
        rows = (await db.execute(sql, params)).mappings().all()
        
        entity_mentions = {}
        articles = []
        
        for row in rows:
            article = dict(row)
            articles.append(article)
            
            if entity_name:
                text_content = f"{article.get('title', '')} {article.get('summary_final', '')}"
                mentions = text_content.lower().count(entity_name.lower())
                if mentions > 0:
                    if entity_name not in entity_mentions:
                        entity_mentions[entity_name] = {"count": 0, "articles": []}
                    entity_mentions[entity_name]["count"] += mentions
                    entity_mentions[entity_name]["articles"].append(article["id"])
        
        return {
            "query": {
                "entity_type": entity_type,
                "entity_name": entity_name,
                "since_days": since_days,
                "limit": limit
            },
            "articles": articles,
            "entity_mentions": entity_mentions,
            "total_articles": len(articles)
        }
        
    except Exception as e:
        # Fallback si pas de colonne entities
        sql_fallback = text("""
            SELECT 
                id, 
                title, 
                canonical_url,
                canonical_url AS url,  -- ✅ AJOUT du champ url
                domain, 
                published_at, 
                lang,
                summary_final
            FROM articles
            WHERE published_at >= :since_dt
              AND (
                CASE 
                    WHEN :entity_name IS NOT NULL THEN 
                        (title ILIKE :entity_pattern OR summary_final ILIKE :entity_pattern)
                    ELSE 
                        (title IS NOT NULL)
                END
              )
            ORDER BY published_at DESC
            LIMIT :limit
        """)
        
        fallback_params = {
            "since_dt": since_dt,
            "entity_name": entity_name,
            "entity_pattern": f"%{entity_name}%" if entity_name else "%",
            "limit": limit
        }
        
        rows = (await db.execute(sql_fallback, fallback_params)).mappings().all()
        
        return {
            "query": {
                "entity_type": entity_type,
                "entity_name": entity_name,
                "since_days": since_days,
                "limit": limit
            },
            "articles": [dict(r) for r in rows],
            "note": "Recherche textuelle simple (colonne entities non disponible)",
            "total_articles": len(rows)
        }

@router.get("/similar/{article_id}")
async def search_similar_articles(
    article_id: int = Path(..., ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_session)
):
    """Trouve des articles similaires basés sur les mots-clés et topics"""
    
    try:
        stmt = select(Article).where(Article.id == article_id)
        result = await db.execute(stmt)
        reference_article = result.scalar_one_or_none()
        
        if not reference_article:
            raise HTTPException(404, f"Article {article_id} non trouvé")
    except Exception as e:
        raise HTTPException(500, f"Erreur lors de la récupération de l'article: {e}")
    
    try:
        title_words = []
        if reference_article.title:
            words = re.findall(r'\b\w{4,}\b', reference_article.title.lower())
            title_words = words[:5]
        
        if not title_words:
            title_words = ["news"]
        
        title_pattern = ' '.join(title_words)
        
        sql = text("""
            SELECT 
                id, 
                title, 
                canonical_url,
                canonical_url AS url,  -- ✅ AJOUT du champ url
                domain, 
                published_at, 
                lang,
                keywords, 
                topics, 
                summary_final,
                CASE 
                    WHEN domain = :ref_domain THEN 3
                    WHEN lang = :ref_lang THEN 2
                    ELSE 1
                END as similarity_score
            FROM articles
            WHERE id != :ref_id
              AND published_at IS NOT NULL
              AND (
                title ILIKE :title_pattern 
                OR summary_final ILIKE :title_pattern
              )
            ORDER BY similarity_score DESC, published_at DESC
            LIMIT :limit
        """)
        
        ref_domain = reference_article.domain or ""
        ref_lang = reference_article.lang or "en"
        
        params = {
            "ref_id": article_id,
            "title_pattern": f"%{title_pattern}%",
            "ref_domain": ref_domain,
            "ref_lang": ref_lang,
            "limit": limit
        }
        
        rows = (await db.execute(sql, params)).mappings().all()
        
        return {
            "reference_article": {
                "id": reference_article.id,
                "title": reference_article.title,
                "url": reference_article.canonical_url,  # ✅ AJOUT
                "domain": reference_article.domain,
                "keywords": reference_article.keywords,
                "topics": reference_article.topics
            },
            "similar_articles": [dict(r) for r in rows],
            "total_found": len(rows),
            "method": "text_and_metadata_similarity"
        }
        
    except Exception as e:
        try:
            sql_simple = text("""
                SELECT 
                    id, 
                    title, 
                    canonical_url,
                    canonical_url AS url,  -- ✅ AJOUT du champ url
                    domain, 
                    published_at, 
                    lang, 
                    summary_final
                FROM articles
                WHERE id != :ref_id
                  AND published_at IS NOT NULL
                  AND domain = :ref_domain
                ORDER BY published_at DESC
                LIMIT :limit
            """)
            
            simple_params = {
                "ref_id": article_id,
                "ref_domain": reference_article.domain or "",
                "limit": limit
            }
            
            rows = (await db.execute(sql_simple, simple_params)).mappings().all()
            
            return {
                "reference_article": {
                    "id": reference_article.id,
                    "title": reference_article.title,
                    "url": reference_article.canonical_url,  # ✅ AJOUT
                    "domain": reference_article.domain
                },
                "similar_articles": [dict(r) for r in rows],
                "method": "same_domain_fallback",
                "total_found": len(rows),
                "note": "Fallback: articles du même domaine"
            }
            
        except Exception as fallback_error:
            raise HTTPException(500, f"Erreur lors de la recherche de similarité: {fallback_error}")