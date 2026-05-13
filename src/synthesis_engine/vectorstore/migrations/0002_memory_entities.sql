-- synthesis_engine memory layer — migration 0002.
--
-- This migration introduces the entity-graph and session/user memory tiers
-- of the three-tier memory architecture. Tier 1 (vector RAG over chunks)
-- continues to live in 0001_initial.sql; this migration is strictly additive
-- and idempotent so it can sit alongside the existing schema in either order
-- a fresh DB or a live DB applies them.
--
-- Design notes:
--
-- * **Bi-temporal, immutable append-only relations.** A fact (relation row)
--   has both a `validity_start` (when the world believes the fact began to
--   hold) and a `validity_end` (when it stopped, or NULL for "still current").
--   Superseding an existing fact is a transactional two-step: (1) UPDATE the
--   prior row's validity_end to `now()`; (2) INSERT a new row with
--   validity_start = `now()`, validity_end = NULL. The two writes happen
--   inside a single transaction in `pgvector_memory.py` so external
--   observers never see a half-superseded state. An optional `supersedes`
--   relation can be inserted in the same transaction to record the audit
--   edge between the prior fact and the replacement; queries can walk it.
--
--   This matches the dominant 2026 shape (Mem0, Zep/Graphiti) where each
--   fact carries a validity window, which keeps the abstract Memory ABC
--   compatible with those backends as drop-in replacements later.
--
-- * **Provenance lives on relations, not entities.** Relations are the
--   temporal events; entities are long-lived nouns. Per-attribute
--   provenance for an entity is encoded inside the entity's `attributes`
--   jsonb as `{key: {value, provenance, updated_at}}` rather than a
--   separate table, so callers can update one attribute without rewriting
--   the entity row (jsonb_set is atomic within a row UPDATE).
--
-- * **Single shared schema across workspaces.** Same convention as
--   migration 0001: workspace column scopes rows; indexes are global. A
--   workspace's entire graph can be pruned with two DELETEs.
--
-- * **Entities may or may not have an embedding.** A `decision` or
--   `concept` extracted from a session may never be embedded. A `document`
--   entity that mirrors a chunk's source likely will be. The HNSW index
--   uses a partial index over `WHERE embedding IS NOT NULL` so we don't
--   pay for empty rows.
--
-- Idempotent: every CREATE uses IF NOT EXISTS.

-- ---------------------------------------------------------------------------
-- entities — nouns in the workspace graph
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS entities (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace   TEXT NOT NULL,
    type        TEXT NOT NULL,             -- e.g., person, concept, document, decision
    name        TEXT NOT NULL,
    -- Attributes are stored as a jsonb map of:
    --   {attr_name: {value: <any>, provenance: {...}, updated_at: <iso ts>}}
    -- Allowing per-attribute provenance without a separate table.
    attributes  JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding   VECTOR(384),                -- nullable; entities are not required to embed
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace, type, name)
);

CREATE INDEX IF NOT EXISTS idx_entities_workspace
    ON entities (workspace);
CREATE INDEX IF NOT EXISTS idx_entities_workspace_type
    ON entities (workspace, type);
CREATE INDEX IF NOT EXISTS idx_entities_workspace_name
    ON entities (workspace, name);

-- GIN over the jsonb attributes lets callers filter on attribute keys
-- and contains-clauses without a sequential scan.
CREATE INDEX IF NOT EXISTS idx_entities_attributes_gin
    ON entities USING GIN (attributes);

-- HNSW only over rows that have an embedding (saves the vacuum/build cost
-- on the NULL majority for entities that never carry vectors).
CREATE INDEX IF NOT EXISTS idx_entities_embedding_hnsw
    ON entities USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
    WHERE embedding IS NOT NULL;

DROP TRIGGER IF EXISTS entities_set_updated_at ON entities;
CREATE TRIGGER entities_set_updated_at
    BEFORE UPDATE ON entities
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- relations — temporal facts connecting entities (bi-temporal append-only)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS relations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace       TEXT NOT NULL,
    from_entity     UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    to_entity       UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    -- Relation type, e.g., authored, cites, contradicts, supersedes,
    -- works_at, located_in, depends_on. A small DSL emerges by convention;
    -- the schema does not enforce a fixed vocabulary so application layers
    -- can extend it without a migration.
    type            TEXT NOT NULL,
    attributes      JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Bi-temporal window. `validity_end IS NULL` means "still current."
    -- A separate `created_at` records when the row was written, which can
    -- differ from `validity_start` (we may record facts retroactively).
    validity_start  TIMESTAMPTZ NOT NULL DEFAULT now(),
    validity_end    TIMESTAMPTZ,
    -- Provenance is REQUIRED on every relation. The application layer is
    -- responsible for populating it; the DB enforces non-null jsonb here
    -- and the pgvector_memory.upsert_relation method validates shape.
    provenance      JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (validity_end IS NULL OR validity_end >= validity_start)
);

CREATE INDEX IF NOT EXISTS idx_relations_workspace_from
    ON relations (workspace, from_entity);
CREATE INDEX IF NOT EXISTS idx_relations_workspace_to
    ON relations (workspace, to_entity);
CREATE INDEX IF NOT EXISTS idx_relations_workspace_type
    ON relations (workspace, type);

-- Hot path: "give me the current facts for this workspace." A partial
-- index over WHERE validity_end IS NULL keeps the live working set small
-- and avoids scanning historical rows.
CREATE INDEX IF NOT EXISTS idx_relations_current
    ON relations (workspace, from_entity, to_entity)
    WHERE validity_end IS NULL;

-- For temporal range queries: GiST on tstzrange built from the validity
-- window. Used by `validity_at` lookups in three_tier_retrieve when the
-- caller asks "what was true at <timestamp>?"
CREATE INDEX IF NOT EXISTS idx_relations_validity_range
    ON relations USING GIST (
        tstzrange(validity_start, COALESCE(validity_end, 'infinity'::timestamptz), '[)')
    );

-- Provenance GIN — supports queries like "show me everything attributed
-- to agent_run_id X" or "facts with confidence >= 0.8."
CREATE INDEX IF NOT EXISTS idx_relations_provenance_gin
    ON relations USING GIN (provenance);

-- ---------------------------------------------------------------------------
-- session_memory — per-session working context
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS session_memory (
    session_id  TEXT PRIMARY KEY,
    user_id     TEXT,
    workspace   TEXT NOT NULL,
    -- Free-form per-session state: scratchpad facts, conversation summary,
    -- pending tool-call state, anything the agent loop needs to recover
    -- after a restart. The agent loop in sub-phase 1.3 will write here.
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_session_memory_workspace
    ON session_memory (workspace);
CREATE INDEX IF NOT EXISTS idx_session_memory_user
    ON session_memory (user_id);

DROP TRIGGER IF EXISTS session_memory_set_updated_at ON session_memory;
CREATE TRIGGER session_memory_set_updated_at
    BEFORE UPDATE ON session_memory
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- user_memory — per-user persistent context (preferences, traits, projects)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS user_memory (
    user_id     TEXT PRIMARY KEY,
    -- Per-user persistent blocks, e.g.:
    --   {persona: {...}, preferences: {...}, projects: [...], pinned_facts: [...]}
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS user_memory_set_updated_at ON user_memory;
CREATE TRIGGER user_memory_set_updated_at
    BEFORE UPDATE ON user_memory
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

-- Ensure pgcrypto / gen_random_uuid is available. pg16's `pgcrypto` ships
-- in contrib; `gen_random_uuid` is in core since pg13. The extension call
-- below is defensive for setups where the system catalog hasn't loaded it.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Record migration as applied.
INSERT INTO schema_migrations (version, description)
VALUES (2, 'memory layer: entities, relations (bi-temporal), session_memory, user_memory')
ON CONFLICT (version) DO NOTHING;
