-- =============================================================================
-- 0029 — Lock down direct poems reads
-- =============================================================================
-- ⚠️  DO NOT APPLY until the 0028 client rollout is verified in production:
--     both anon and signed-in reading paths must be confirmed working against
--     the new RPCs (recommend_poems no-user_id overload, get_poem,
--     get_poems_by_ids). Applying this while any client is still doing
--     .from('poems').select(...) will break that client immediately.
--
-- After application:
--   - anon and authenticated roles can no longer SELECT from public.poems
--     directly. All read access flows through the security-definer functions
--     introduced in 0028.
--   - the old recommend_poems(uuid, ...) overload is removed, so PostgREST
--     no longer dispatches to it. Any lingering client sending user_id_in
--     will get a "function not found" error.
--   - service-role writes (ingest scripts, admin) are unaffected — service
--     role bypasses table grants and RLS.
-- =============================================================================

drop policy if exists "poems: authenticated read" on poems;
drop policy if exists "poems: anon read"          on poems;

revoke select on public.poems from anon;
revoke select on public.poems from authenticated;

drop function if exists recommend_poems(uuid, int, boolean, boolean, boolean, text[], boolean);
