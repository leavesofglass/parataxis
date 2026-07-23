-- =============================================================================
-- 0020 — Add missing interaction_action enum values
-- =============================================================================
-- Migrations 0016 and 0019 added 'like', 'unlike', 'share', and 'undislike'
-- to the recommend_poems RPC and the app's interaction log calls, but never
-- extended the enum. The RPC fails at parse time even for zero-row queries
-- because PostgreSQL validates enum casts before execution.
-- =============================================================================

alter type interaction_action add value if not exists 'like';
alter type interaction_action add value if not exists 'unlike';
alter type interaction_action add value if not exists 'share';
alter type interaction_action add value if not exists 'undislike';
