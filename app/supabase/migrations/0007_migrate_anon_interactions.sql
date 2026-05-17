-- =============================================================================
-- 0007_migrate_anon_interactions
-- =============================================================================
-- Moves all interactions from an anonymous user_id to the calling
-- (authenticated) user_id, atomically.
--
-- Used by the magic-link callback when an anon user signs in to an existing
-- account: without this, the anon user's saves/super-likes are orphaned.
--
-- Guards:
--   * caller must be authenticated
--   * source user_id must differ from caller (no self-migration)
--   * source profile must still be is_anonymous = true (prevents stealing
--     interactions from a real account)
-- =============================================================================

create or replace function migrate_anon_interactions(anon_user_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  caller uuid := auth.uid();
begin
  if caller is null then
    raise exception 'must be authenticated';
  end if;

  if caller = anon_user_id then
    raise exception 'cannot migrate from self';
  end if;

  if not exists (
    select 1 from profiles
    where id = anon_user_id and is_anonymous = true
  ) then
    raise exception 'source user is not an anonymous account';
  end if;

  insert into interactions (user_id, poem_id, action, created_at)
  select caller, poem_id, action, created_at
  from interactions
  where user_id = anon_user_id;

  delete from interactions where user_id = anon_user_id;
end;
$$;

grant execute on function migrate_anon_interactions(uuid) to authenticated;
