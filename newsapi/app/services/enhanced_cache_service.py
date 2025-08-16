# app/services/enhanced_cache_service.py
import asyncio
import json
import hashlib
import logging
from typing import Any, Optional, Union, Dict, List
from datetime import datetime
import os

logger = logging.getLogger(__name__)

# Import conditionnel de Redis
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, cache will be disabled")

class EnhancedCacheService:
    """Service de cache avancé pour NewsAI"""
    
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        self.redis_pool = None
        self._stats = {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0}
        self._memory_cache = {}  # Fallback en mémoire
    
    async def init(self):
        """Initialisation du pool Redis"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, using memory cache")
            return
            
        try:
            self.redis_pool = redis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=20,
                decode_responses=True,
                retry_on_timeout=True
            )
            async with redis.Redis(connection_pool=self.redis_pool) as r:
                await r.ping()
            logger.info("✅ Enhanced cache service initialized")
        except Exception as e:
            logger.error(f"❌ Cache initialization failed: {e}")
            self.redis_pool = None
    
    def _make_key(self, namespace: str, key: str) -> str:
        """Génère une clé cache avec namespace"""
        return f"newsai:{namespace}:{key}"
    
    def _hash_key(self, data: Union[str, dict, list]) -> str:
        """Génère un hash pour des clés complexes"""
        if isinstance(data, (dict, list)):
            data = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    async def get(self, namespace: str, key: str, default: Any = None) -> Any:
        """Récupère une valeur du cache"""
        if not REDIS_AVAILABLE or not self.redis_pool:
            # Fallback mémoire
            cache_key = self._make_key(namespace, key)
            if cache_key in self._memory_cache:
                self._stats['hits'] += 1
                return self._memory_cache[cache_key]
            self._stats['misses'] += 1
            return default
        
        try:
            async with redis.Redis(connection_pool=self.redis_pool) as r:
                cache_key = self._make_key(namespace, key)
                value = await r.get(cache_key)
                
                if value is not None:
                    self._stats['hits'] += 1
                    return json.loads(value)
                else:
                    self._stats['misses'] += 1
                    return default
                    
        except Exception as e:
            self._stats['errors'] += 1
            logger.warning(f"Cache get error for {namespace}:{key}: {e}")
            return default
    
    async def set(self, namespace: str, key: str, value: Any, ttl: int = 3600) -> bool:
        """Stocke une valeur dans le cache"""
        if not REDIS_AVAILABLE or not self.redis_pool:
            # Fallback mémoire (simple, sans TTL)
            cache_key = self._make_key(namespace, key)
            self._memory_cache[cache_key] = value
            self._stats['sets'] += 1
            return True
        
        try:
            async with redis.Redis(connection_pool=self.redis_pool) as r:
                cache_key = self._make_key(namespace, key)
                serialized = json.dumps(value, default=str)
                
                await r.setex(cache_key, ttl, serialized)
                self._stats['sets'] += 1
                return True
                
        except Exception as e:
            self._stats['errors'] += 1
            logger.warning(f"Cache set error for {namespace}:{key}: {e}")
            return False
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalide toutes les clés matchant un pattern"""
        if not REDIS_AVAILABLE or not self.redis_pool:
            # Fallback mémoire
            count = 0
            keys_to_remove = []
            for key in self._memory_cache:
                if pattern in key or pattern == "*":
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self._memory_cache[key]
                count += 1
            return count
        
        try:
            async with redis.Redis(connection_pool=self.redis_pool) as r:
                keys = await r.keys(f"newsai:{pattern}")
                if keys:
                    deleted = await r.delete(*keys)
                    logger.info(f"Invalidated {deleted} cache keys matching {pattern}")
                    return deleted
                return 0
                
        except Exception as e:
            self._stats['errors'] += 1
            logger.warning(f"Cache invalidation error for {pattern}: {e}")
            return 0
    
    async def get_stats(self) -> dict:
        """Retourne les statistiques du cache"""
        total_ops = self._stats['hits'] + self._stats['misses']
        hit_rate = (self._stats['hits'] / total_ops * 100) if total_ops > 0 else 0
        
        redis_info = {}
        if REDIS_AVAILABLE and self.redis_pool:
            try:
                async with redis.Redis(connection_pool=self.redis_pool) as r:
                    info = await r.info('memory')
                    redis_info = {
                        'used_memory_human': info.get('used_memory_human'),
                        'connected_clients': info.get('connected_clients'),
                        'keyspace_hits': info.get('keyspace_hits', 0),
                        'keyspace_misses': info.get('keyspace_misses', 0)
                    }
            except Exception as e:
                logger.warning(f"Failed to get Redis stats: {e}")
        
        return {
            'app_stats': {
                **self._stats,
                'hit_rate': round(hit_rate, 2),
                'total_operations': total_ops
            },
            'redis_stats': redis_info,
            'status': 'connected' if (REDIS_AVAILABLE and self.redis_pool) else 'memory_fallback',
            'memory_cache_size': len(self._memory_cache)
        }

# Instance globale
cache = EnhancedCacheService()

# Middleware de cache intelligent
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class SmartCacheMiddleware(BaseHTTPMiddleware):
    """Middleware de cache intelligent"""
    
    CACHE_STRATEGIES = {
        "/api/v1/sources": 3600,  # 1h
        "/api/v1/articles": 900,  # 15min
        "/api/v1/topics": 600,  # 10min
        "/api/v1/stats": 300,  # 5min
        "/health": 60,  # 1min
        "/api/v1/summaries": 900,            # 15 min
        "/api/v1/summaries/source": 1800,    # 30 min
        "/api/v1/summaries/trending": 600,   # 10 min
        "/api/v1/synthesis": 900             # 15 min
    }
    
    async def dispatch(self, request: Request, call_next):
        if request.method != "GET":
            return await call_next(request)
        
        path = request.url.path
        query = str(request.url.query)
        
        # Vérifier si le endpoint a une stratégie de cache
        ttl = None
        for pattern, cache_ttl in self.CACHE_STRATEGIES.items():
            if path.startswith(pattern):
                ttl = cache_ttl
                break
        
        if ttl is None:
            return await call_next(request)
        
        # Génération de la clé de cache
        cache_key = cache._hash_key(f"{path}?{query}")
        
        # Tentative de récupération depuis le cache
        cached_response = await cache.get("api_responses", cache_key)
        if cached_response:
            return Response(
                content=cached_response["body"],
                status_code=cached_response["status_code"],
                headers=cached_response["headers"],
                media_type=cached_response["media_type"]
            )
        
        # Exécution de la requête
        response = await call_next(request)
        
        # Mise en cache si succès
        if response.status_code == 200:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            cache_data = {
                "body": body.decode(),
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type
            }
            
            await cache.set("api_responses", cache_key, cache_data, ttl)
            
            return Response(
                content=body,
                status_code=response.status_code,
                headers=response.headers,
                media_type=response.media_type
            )
        
        return response