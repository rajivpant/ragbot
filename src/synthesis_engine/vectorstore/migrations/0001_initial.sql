-- Ragbot pgvector backend — initial schema (migration 0001).
--
-- Design notes:
--   * Single shared schema across all workspaces. The `workspace` column
--     scopes rows; HNSW + GIN indexes are global. This trades per-workspace
--     isolation for cross-workspace queryability and simpler ops.
--   * `documents` row per source file (stable identity by workspace+source_path).
--   * `chunks` row per chunk, FK-cascaded to its document so workspace cleanup
--     is one DELETE.
--   * `embedding_model` is stored on chunks so a future embedding-model swap
--     can re-embed selectively without throwing away existing rows.
--   * `text_search` is a generated tsvector for native Postgres full-text
--     search, replacing the in-process BM25 implementation.
--   * `metadata` JSONB lets the chunker stash arbitrary fields without
--     schema changes.
--
-- Idempotent: every CREATE uses IF NOT EXISTS. Re-running this migration is safe.

CREATE EXTENSION IF NOT EXISTS vector;

-- Schema version table — tracks applied migrations.
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    description TEXT NOT NULL
);

-- Workspaces table — optional metadata, primarily a referential anchor.
CREATE TABLE IF NOT EXISTS workspaces (
    name         TEXT PRIMARY KEY,
    display_name TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Documents table — one row per source file per workspace.
CREATE TABLE IF NOT EXISTS documents (
    id              BIGSERIAL PRIMARY KEY,
    workspace       TEXT NOT NULL,
    source_path     TEXT NOT NULL,
    filename        TEXT NOT NULL,
    title           TEXT,
    content_type    TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    indexed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    embedding_model TEXT NOT NULL,
    UNIQUE (workspace, source_path)
);

CREATE INDEX IF NOT EXISTS idx_documents_workspace
    ON documents (workspace);
CREATE INDEX IF NOT EXISTS idx_documents_workspace_content_type
    ON documents (workspace, content_type);

-- Chunks table — one row per text chunk with embedding + FTS vector.
CREATE TABLE IF NOT EXISTS chunks (
    id              BIGSERIAL PRIMARY KEY,
    document_id     BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    workspace       TEXT NOT NULL,           -- denormalized for fast filtering
    chunk_index     INTEGER NOT NULL,
    chunk_uid       TEXT NOT NULL,           -- deterministic chunk id (stable across reindex)
    text            TEXT NOT NULL,
    char_start      INTEGER,
    char_end        INTEGER,
    embedding       VECTOR(384) NOT NULL,
    embedding_model TEXT NOT NULL,
    content_type    TEXT,
    filename        TEXT,
    title           TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    text_search     TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace, chunk_uid)
);

CREATE INDEX IF NOT EXISTS idx_chunks_workspace
    ON chunks (workspace);
CREATE INDEX IF NOT EXISTS idx_chunks_workspace_content_type
    ON chunks (workspace, content_type);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id
    ON chunks (document_id);

-- Vector index: HNSW with cosine distance. m and ef_construction tuned for
-- the typical workspace size (10s of thousands of chunks). Adjust if dataset
-- grows substantially.
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Full-text search index for hybrid retrieval (replaces in-process BM25).
CREATE INDEX IF NOT EXISTS idx_chunks_text_search
    ON chunks USING GIN (text_search);

-- Trigger to keep updated_at fresh on chunks.
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS chunks_set_updated_at ON chunks;
CREATE TRIGGER chunks_set_updated_at
    BEFORE UPDATE ON chunks
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS workspaces_set_updated_at ON workspaces;
CREATE TRIGGER workspaces_set_updated_at
    BEFORE UPDATE ON workspaces
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- Record migration as applied.
INSERT INTO schema_migrations (version, description)
VALUES (1, 'initial schema: workspaces, documents, chunks with pgvector + tsvector')
ON CONFLICT (version) DO NOTHING;
