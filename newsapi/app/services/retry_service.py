# app/services/retry_service.py
import asyncio
import logging
from functools import wraps
from typing import Callable, Any, Optional, Union
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class RetryConfig:
    """Configuration centralisée pour les retry policies"""
    HTTP_MAX_ATTEMPTS = 3
    HTTP_MIN_WAIT = 1
    HTTP_MAX_WAIT = 10
    HTTP_TIMEOUT = 30
    DB_MAX_ATTEMPTS = 5
    DB_MIN_WAIT = 0.5
    DB_MAX_WAIT = 5
    API_MAX_ATTEMPTS = 3
    API_MIN_WAIT = 2
    API_MAX_WAIT = 30

def http_retry(max_attempts: int = RetryConfig.HTTP_MAX_ATTEMPTS):
    """Décorateur pour retry automatique des requêtes HTTP"""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=RetryConfig.HTTP_MIN_WAIT, max=RetryConfig.HTTP_MAX_WAIT),
        retry=retry_if_exception_type((
            aiohttp.ClientError,
            aiohttp.ServerTimeoutError,
            asyncio.TimeoutError,
            ConnectionError
        )),
        before_sleep=lambda retry_state: logger.warning(
            f"HTTP retry {retry_state.attempt_number}/{max_attempts}: {retry_state.outcome.exception()}"
        )
    )

def db_retry(max_attempts: int = RetryConfig.DB_MAX_ATTEMPTS):
    """Décorateur pour retry automatique des opérations DB"""
    from sqlalchemy.exc import OperationalError, DisconnectionError
    
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=RetryConfig.DB_MIN_WAIT, max=RetryConfig.DB_MAX_WAIT),
        retry=retry_if_exception_type((
            OperationalError,
            DisconnectionError,
            ConnectionError
        )),
        before_sleep=lambda retry_state: logger.warning(
            f"DB retry {retry_state.attempt_number}/{max_attempts}: {retry_state.outcome.exception()}"
        )
    )

def monitor_performance(operation_name: str):
    """Décorateur pour monitorer les performances des opérations"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(f"✅ {operation_name} completed in {duration:.2f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"❌ {operation_name} failed after {duration:.2f}s: {e}")
                raise
        
        return wrapper
    return decorator

class RobustHTTPSession:
    """Session HTTP avec retry automatique"""
    
    def __init__(self, timeout: int = RetryConfig.HTTP_TIMEOUT):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    @http_retry()
    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """GET robuste avec retry automatique"""
        return await self.session.get(url, **kwargs)
    
    @http_retry()
    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """POST robuste avec retry automatique"""
        return await self.session.post(url, **kwargs)

async def robust_fetch_feed(feed_url: str, etag: str = None, last_modified: str = None):
    """Version robuste de fetch_feed avec retry automatique"""
    
    @http_retry()
    async def _fetch():
        async with RobustHTTPSession() as session:
            headers = {}
            if etag:
                headers["If-None-Match"] = etag
            if last_modified:
                headers["If-Modified-Since"] = last_modified
            
            response = await session.get(feed_url, headers=headers)
            return response.status, response
    
    try:
        return await _fetch()
    except Exception as e:
        logger.error(f"Failed to fetch feed {feed_url} after retries: {e}")
        return 500, None

async def robust_enrich_html(url: str, timeout: int = 15):
    """Version robuste de enrich_html avec retry et timeout"""
    
    @http_retry(max_attempts=2)
    async def _enrich():
        async with RobustHTTPSession(timeout=timeout) as session:
            response = await session.get(url)
            if response.status == 200:
                content = await response.text()
                return {"full_text": content, "status": "success"}
            return {"full_text": None, "status": f"error_{response.status}"}
    
    try:
        return await _enrich()
    except Exception as e:
        logger.warning(f"HTML enrichment failed for {url}: {e}")
        return {"full_text": None, "status": "failed"}