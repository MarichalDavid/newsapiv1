from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, desc
from ..core.db import get_session
from ..core.models import Article

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

@router.get("")
async def search_articles(
    q: str = Query(..., description="Requête de recherche obligatoire"),
    limit: int = Query(20, ge=1, le=100),
    lang: str | None = None,
    db: AsyncSession = Depends(get_session)
):
    """Recherche globale d'articles"""
    # Construire conditions WHERE
    conditions = ["title ILIKE :q OR summary_final ILIKE :q"]
    params = {"q": f"%{q}%", "limit": limit}
    
    if lang:
        conditions.append("lang = :lang")
        params["lang"] = lang
    
    where_clause = " AND ".join(conditions)
    
    sql = text(f"""
        SELECT id, title, canonical_url, domain, published_at, lang, 
               keywords, topics, summary_final, summary_source
        FROM articles
        WHERE {where_clause}
        ORDER BY published_at DESC NULLS LAST
        LIMIT :limit
    """)
    
    rows = (await db.execute(sql, params)).mappings().all()
    return [dict(r) for r in rows]

# ✅ NOUVEAU: Recherche d'entités
@router.get("/entities")
async def search_entities(
    entity_type: str = Query(..., description="Type d'entité: PERSON, ORG, LOCATION, etc."),
    entity_name: str = Query(None, description="Nom de l'entité à rechercher"),
    limit: int = Query(50, ge=1, le=200),
    since_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_session)
):
    """Recherche d'articles par entités nommées"""
    
    # Si on a un nom d'entité spécifique
    if entity_name:
        # Recherche par nom d'entité dans le texte
        sql = text("""
            SELECT 
                id, title, canonical_url, domain, published_at, lang,
                summary_final, entities
            FROM articles
            WHERE published_at >= NOW() - (:days || ' days')::interval
              AND (
                title ILIKE :entity_pattern 
                OR summary_final ILIKE :entity_pattern
                OR full_text ILIKE :entity_pattern
              )
            ORDER BY published_at DESC
            LIMIT :limit
        """)
        
        entity_pattern = f"%{entity_name}%"
        params = {"days": str(since_days), "entity_pattern": entity_pattern, "limit": limit}
        
    else:
        # Recherche par type d'entité (si vous avez une colonne entities JSON)
        sql = text("""
            SELECT 
                id, title, canonical_url, domain, published_at, lang,
                summary_final, entities
            FROM articles
            WHERE published_at >= NOW() - (:days || ' days')::interval
              AND entities IS NOT NULL
              AND entities::text ILIKE :entity_type_pattern
            ORDER BY published_at DESC
            LIMIT :limit
        """)
        
        entity_type_pattern = f"%{entity_type}%"
        params = {"days": str(since_days), "entity_type_pattern": entity_type_pattern, "limit": limit}
    
    try:
        rows = (await db.execute(sql, params)).mappings().all()
        
        # Extraire et compter les entités
        entity_mentions = {}
        articles = []
        
        for row in rows:
            article = dict(row)
            articles.append(article)
            
            # Si vous avez une recherche par nom, compter les mentions
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
        # Recherche simple dans le texte
        sql_fallback = text("""
            SELECT 
                id, title, canonical_url, domain, published_at, lang,
                summary_final
            FROM articles
            WHERE published_at >= NOW() - (:days || ' days')::interval
              AND (
                CASE 
                    WHEN :entity_name IS NOT NULL THEN 
                        (title ILIKE :entity_pattern OR summary_final ILIKE :entity_pattern)
                    ELSE 
                        (title IS NOT NULL)  -- Retourne tous si pas de nom spécifique
                END
              )
            ORDER BY published_at DESC
            LIMIT :limit
        """)
        
        fallback_params = {
            "days": str(since_days),
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

# ✅ NOUVEAU: Articles similaires
@router.get("/similar/{article_id}")
async def search_similar_articles(
    article_id: int = Path(..., ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_session)
):
    """Trouve des articles similaires basés sur les mots-clés et topics"""
    
    # Récupérer l'article de référence
    stmt = select(Article).where(Article.id == article_id)
    result = await db.execute(stmt)
    reference_article = result.scalar_one_or_none()
    
    if not reference_article:
        raise HTTPException(404, f"Article {article_id} non trouvé")
    
    # Recherche par mots-clés et topics similaires
    similar_conditions = []
    params = {"ref_id": article_id, "limit": limit}
    
    if reference_article.keywords:
        # Recherche par mots-clés communs
        keywords_pattern = "|".join(reference_article.keywords[:5])  # Top 5 mots-clés
        similar_conditions.append("keywords && :ref_keywords")
        params["ref_keywords"] = reference_article.keywords[:5]
    
    if reference_article.topics:
        # Recherche par topics communs
        similar_conditions.append("topics && :ref_topics")
        params["ref_topics"] = reference_article.topics
    
    if reference_article.domain:
        # Même domaine (bonus de similarité)
        similar_conditions.append("domain = :ref_domain")
        params["ref_domain"] = reference_article.domain
    
    if not similar_conditions:
        # Fallback: recherche textuelle
        similar_conditions = ["title ILIKE :title_pattern OR summary_final ILIKE :title_pattern"]
        title_words = reference_article.title.split()[:3] if reference_article.title else [""]
        params["title_pattern"] = f"%{' '.join(title_words)}%"
    
    # Construire la requête
    where_clause = f"id != :ref_id AND published_at IS NOT NULL AND ({' OR '.join(similar_conditions)})"
    
    sql = text(f"""
        SELECT 
            id, title, canonical_url, domain, published_at, lang,
            keywords, topics, summary_final,
            CASE 
                WHEN keywords && :ref_keywords THEN 2
                WHEN topics && :ref_topics THEN 3  
                WHEN domain = :ref_domain THEN 1
                ELSE 0
            END as similarity_score
        FROM articles
        WHERE {where_clause}
        ORDER BY similarity_score DESC, published_at DESC
        LIMIT :limit
    """)
    
    try:
        rows = (await db.execute(sql, params)).mappings().all()
        
        return {
            "reference_article": {
                "id": reference_article.id,
                "title": reference_article.title,
                "domain": reference_article.domain,
                "keywords": reference_article.keywords,
                "topics": reference_article.topics
            },
            "similar_articles": [dict(r) for r in rows],
            "total_found": len(rows)
        }
        
    except Exception as e:
        # Fallback simple si erreur avec les arrays
        sql_simple = text("""
            SELECT id, title, canonical_url, domain, published_at, lang, summary_final
            FROM articles
            WHERE id != :ref_id
              AND published_at IS NOT NULL
              AND (title ILIKE :title_pattern OR summary_final ILIKE :title_pattern)
            ORDER BY published_at DESC
            LIMIT :limit
        """)
        
        title_words = reference_article.title.split()[:3] if reference_article.title else ["news"]
        simple_params = {
            "ref_id": article_id,
            "title_pattern": f"%{' '.join(title_words)}%",
            "limit": limit
        }
        
        rows = (await db.execute(sql_simple, simple_params)).mappings().all()
        
        return {
            "reference_article": {
                "id": reference_article.id,
                "title": reference_article.title,
                "domain": reference_article.domain
            },
            "similar_articles": [dict(r) for r in rows],
            "method": "text_similarity_fallback",
            "total_found": len(rows)
        }