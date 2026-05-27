-- =============================================================================
-- 0008_add_poem_enrichment_columns
-- =============================================================================
-- Adds five 0-10 rubric scores, a short interpretive summary, and an
-- enrichment timestamp to poems. The `embedding vector(1536)` column already
-- exists (migration 0001) and is not touched.
--
-- Idempotency for the enrichment pipeline relies on enriched_at IS NULL
-- meaning "not yet enriched"; every existing row is NULL after this migration.
-- =============================================================================

alter table poems
  add column emotional_intensity smallint check (emotional_intensity between 0 and 10),
  add column intellectual_demand smallint check (intellectual_demand between 0 and 10),
  add column sensory_richness    smallint check (sensory_richness    between 0 and 10),
  add column formal_structure    smallint check (formal_structure    between 0 and 10),
  add column voice_register      smallint check (voice_register      between 0 and 10),
  add column summary             text,
  add column enriched_at         timestamptz;

-- Partial index for the pipeline's "give me unenriched poems" query.
create index poems_unenriched_idx
  on poems (id) where enriched_at is null;
