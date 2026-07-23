-- =============================================================================
-- 0017_add_translator_column
-- =============================================================================
-- Adds an optional translator text column to the poems table.
-- Populated only for translated poems; NULL (or '') for originals.
-- Contains the bare translator name(s) — "Translated by" prefix is stripped
-- at ingest time by bilingual_filter.py.
-- =============================================================================

alter table poems
  add column if not exists translator text not null default '';
