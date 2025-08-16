from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Any
from datetime import datetime

class SourceIn(BaseModel):
    name: str
    feed_url: str
    site_domain: str
    method: str = "rss"
    enrichment: str = "none"
    frequency_minutes: int = 10
    active: bool = True

class SourceOut(SourceIn):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ArticleOut(BaseModel):
    id: int
    source_id: int
    url: str
    canonical_url: str
    domain: str
    title: str
    summary_feed: Optional[str] = None
    published_at: Optional[datetime] = None
    authors: Optional[List[str]] = None
    full_text: Optional[str] = None
    lang: Optional[str] = None
    summary_final: Optional[str] = None
    fetched_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class Config:
    from_attributes = True

class ArticleDetail(ArticleOut):
    summary_feed: Optional[str] = None
    full_text: Optional[str] = None
    entities: Optional[Any] = None
    jsonld: Optional[Any] = None
    raw: Optional[Any] = None

class Filters(BaseModel):
    q: Optional[str] = None
    topic: Optional[List[str]] = None
    region: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    lang: Optional[List[str]] = None
    source_id: Optional[List[int]] = None
    domain: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    has_full_text: Optional[bool] = None
    summary_source: Optional[str] = None
    order_by: Optional[str] = "published_at"
    order: Optional[str] = "desc"
    limit: int = 50
    offset: int = 0

class SummaryRequest(Filters):
    target_sentences: int = 10
    include_bullets: bool = False

class SummaryResponse(BaseModel):
    total_articles: int
    used_articles: int
    summary_text: str
    topics_hint: List[str] = []
    keywords_hint: List[str] = []
