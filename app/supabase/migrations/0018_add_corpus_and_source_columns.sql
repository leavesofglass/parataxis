-- =============================================================================
-- 0018 — Add corpus tag and extended rubric columns
-- =============================================================================
-- New corpus (10 k poems from RALP / Slowdown / VerseDaily / PoetryDaily)
-- brings a corpus tag and different rubric dimensions.
--
-- Already present (NOT touched):
--   line_count          — initial schema
--   translator          — 0017
--   emotional_intensity — 0008 (shared dimension; used by both corpora)
--   summary, enriched_at — 0008
--   intellectual_demand, sensory_richness, formal_structure, voice_register — 0008
--     (old dimensions, NULL for new poems)
--
-- pgvector HNSW index (poems_embedding_hnsw) was created in 0009 and
-- auto-covers new inserts — no index migration needed here.
-- =============================================================================

alter table poems
  add column if not exists corpus        text,
  add column if not exists mood          smallint check (mood          between 0 and 10),
  add column if not exists imagery       smallint check (imagery       between 0 and 10),
  add column if not exists accessibility smallint check (accessibility between 0 and 10),
  add column if not exists formality     smallint check (formality     between 0 and 10);
