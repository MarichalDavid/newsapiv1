-- Tables
CREATE TABLE IF NOT EXISTS sources (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  feed_url TEXT NOT NULL UNIQUE,
  site_domain TEXT NOT NULL,
  method TEXT NOT NULL CHECK (method IN ('rss','api','sitemap')) DEFAULT 'rss',
  enrichment TEXT NOT NULL CHECK (enrichment IN ('none','html')) DEFAULT 'none',
  frequency_minutes INT NOT NULL DEFAULT 10,
  etag TEXT,
  last_modified TEXT,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS articles (
  id BIGSERIAL PRIMARY KEY,
  source_id INT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  canonical_url TEXT NOT NULL,
  domain TEXT NOT NULL,
  title TEXT NOT NULL,
  summary_feed TEXT,
  published_at TIMESTAMPTZ,
  authors TEXT[],
  full_text TEXT,
  jsonld JSONB,
  lang VARCHAR(8),
  keywords TEXT[],
  entities JSONB,
  summary_llm TEXT,
  summary_final TEXT,
  summary_source VARCHAR(12) CHECK (summary_source IN ('feed','llm','extractive')),
  topics TEXT[],
  content_hash CHAR(64) NOT NULL,
  simhash BIGINT,
  cluster_id TEXT,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status VARCHAR(16) NOT NULL DEFAULT 'new',
  raw JSONB
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_articles_canonical ON articles(canonical_url);
CREATE INDEX IF NOT EXISTS ix_articles_published_desc ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS ix_articles_domain ON articles(domain);
CREATE INDEX IF NOT EXISTS ix_articles_lang ON articles(lang);
CREATE INDEX IF NOT EXISTS ix_articles_content_hash ON articles USING HASH(content_hash);
CREATE INDEX IF NOT EXISTS ix_articles_cluster ON articles(cluster_id);

-- LLM cache
CREATE TABLE IF NOT EXISTS llm_cache (
  id BIGSERIAL PRIMARY KEY,
  cache_key TEXT NOT NULL UNIQUE,
  model TEXT NOT NULL,
  params JSONB,
  response TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- New columns on articles
ALTER TABLE IF EXISTS articles
  ADD COLUMN IF NOT EXISTS sentiment_label TEXT,
  ADD COLUMN IF NOT EXISTS sentiment_score REAL,
  ADD COLUMN IF NOT EXISTS embed_title_summary vector(384);

-- HNSW index for embeddings
DO $$ BEGIN
  EXECUTE 'CREATE INDEX IF NOT EXISTS idx_articles_embed_hnsw ON articles USING hnsw (embed_title_summary vector_cosine_ops)';
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'Index creation skipped: %', SQLERRM;
END $$;

-- Additional tables
CREATE TABLE IF NOT EXISTS authors(
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  domain TEXT,
  lang TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(name, domain)
);

CREATE TABLE IF NOT EXISTS topic_models(
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT now(),
  model_path TEXT NOT NULL,
  embedding_model TEXT,
  params JSONB
);

CREATE TABLE IF NOT EXISTS entities(
  id SERIAL PRIMARY KEY,
  canonical_name TEXT NOT NULL,
  type TEXT NOT NULL,
  wikidata_id TEXT,
  aliases TEXT[] DEFAULT '{}',
  UNIQUE(canonical_name, type)
);

CREATE TABLE IF NOT EXISTS entity_mentions(
  id BIGSERIAL PRIMARY KEY,
  article_id BIGINT REFERENCES articles(id) ON DELETE CASCADE,
  entity_id INT REFERENCES entities(id) ON DELETE CASCADE,
  sentence_idx INT,
  salience REAL
);

CREATE TABLE IF NOT EXISTS facts(
  id BIGSERIAL PRIMARY KEY,
  article_id BIGINT REFERENCES articles(id) ON DELETE CASCADE,
  subj_entity_id INT REFERENCES entities(id),
  relation TEXT,
  obj_entity_id INT REFERENCES entities(id),
  confidence REAL,
  sentence_idx INT
);

CREATE TABLE IF NOT EXISTS topic_sentiment_daily(
  d DATE,
  topic_id INT,
  pos_count INT DEFAULT 0,
  neu_count INT DEFAULT 0,
  neg_count INT DEFAULT 0,
  PRIMARY KEY(d, topic_id)
);

CREATE TABLE IF NOT EXISTS source_sentiment_daily(
  d DATE,
  domain TEXT,
  pos_count INT DEFAULT 0,
  neu_count INT DEFAULT 0,
  neg_count INT DEFAULT 0,
  PRIMARY KEY(d, domain)
);

CREATE TABLE IF NOT EXISTS author_sentiment_daily(
  d DATE,
  author_id INT,
  pos_count INT DEFAULT 0,
  neu_count INT DEFAULT 0,
  neg_count INT DEFAULT 0,
  avg_score REAL DEFAULT 0,
  PRIMARY KEY(d, author_id)
);

CREATE TABLE IF NOT EXISTS source_relations_daily(
  d DATE,
  src_domain TEXT,
  dst_domain TEXT,
  relation TEXT,
  weight REAL,
  PRIMARY KEY(d, src_domain, dst_domain, relation)
);

-- Materialized view for topics by day
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_topics_daily AS
SELECT date_trunc('day', published_at)::date AS d,
       COALESCE(NULLIF((topics)[1], NULL), 'Unknown') AS topic_label, -- simple placeholder if keyword topics exist
       -1 AS topic_id,
       COUNT(*)::bigint AS c
FROM articles
WHERE published_at IS NOT NULL
GROUP BY 1,2;

CREATE INDEX IF NOT EXISTS idx_mv_topics_daily ON mv_topics_daily(d DESC, topic_label);
