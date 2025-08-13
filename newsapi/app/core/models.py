from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, BigInteger, ARRAY
from sqlalchemy.orm import relationship
from .db import Base
from datetime import datetime

class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    feed_url = Column(Text, nullable=False, unique=True)
    site_domain = Column(Text, nullable=False)
    method = Column(String(12), nullable=False, default="rss")
    enrichment = Column(String(12), nullable=False, default="none")
    frequency_minutes = Column(Integer, nullable=False, default=10)
    etag = Column(Text, nullable=True)
    last_modified = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    

    articles = relationship("Article", back_populates="source")

class LlmCache(Base):
    __tablename__ = "llm_cache"
    id = Column(BigInteger, primary_key=True)
    cache_key = Column(Text, nullable=False, unique=True)
    model = Column(Text, nullable=False)
    params = Column(JSON, nullable=True)
    response = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class Article(Base):
    __tablename__ = "articles"
    id = Column(BigInteger, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    url = Column(Text, nullable=False)
    canonical_url = Column(Text, nullable=False)
    domain = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    summary_feed = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    authors = Column(ARRAY(Text), nullable=True)
    full_text = Column(Text, nullable=True)
    jsonld = Column(JSON, nullable=True)
    lang = Column(String(8), nullable=True)
    keywords = Column(ARRAY(Text), nullable=True)
    entities = Column(JSON, nullable=True)
    summary_llm = Column(Text, nullable=True)
    summary_final = Column(Text, nullable=True)
    summary_source = Column(String(12), nullable=True)
    topics = Column(ARRAY(Text), nullable=True)
    content_hash = Column(String(64), nullable=False)
    simhash = Column(BigInteger, nullable=True)
    cluster_id = Column(Text, nullable=True)
    fetched_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(String(16), nullable=False, default="new")
    raw = Column(JSON, nullable=True)

    source = relationship("Source", back_populates="articles")
