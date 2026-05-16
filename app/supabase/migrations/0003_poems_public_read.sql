-- =============================================================================
-- Make poems readable by all Supabase roles.
--
-- Why: poems table was created via direct SQL query, which doesn't
-- automatically apply Supabase's default PostgREST grants to `anon` and
-- `authenticated`. Without table-level GRANTs, RLS policies can't fire.
--
-- For a public-domain poetry corpus, reads should be open to everyone —
-- anonymous visitors before sign-in and signed-in (including anon-auth) users.
-- =============================================================================

-- Table-level grants (required even when RLS policies exist)
grant select on public.poems to anon;
grant select on public.poems to authenticated;

-- Drop the authenticated-only policy from the initial migration
drop policy if exists "poems: authenticated read" on poems;

-- Replace with policies covering both roles explicitly
create policy "poems: authenticated read"
  on poems for select
  to authenticated
  using (true);

create policy "poems: anon read"
  on poems for select
  to anon
  using (true);
