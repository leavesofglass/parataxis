-- =============================================================================
-- Grant table-level privileges to service_role
--
-- service_role has BYPASSRLS but still needs explicit table grants in Postgres.
-- These were not automatically applied when the schema was created via the
-- Management API query path (as opposed to supabase db push).
-- =============================================================================

grant select, insert, update, delete on public.poems        to service_role;
grant select, insert, update, delete on public.profiles     to service_role;
grant select, insert, update, delete on public.interactions to service_role;
