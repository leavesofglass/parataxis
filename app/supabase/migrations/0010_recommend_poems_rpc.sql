-- =============================================================================
-- 0010_recommend_poems_rpc
-- =============================================================================
-- recommend_poems(user_id_in, limit_in) — returns `limit_in` poems shaped for
-- the swiper deck.
--
-- Algorithm
--   1. Collapse interactions to the latest action per poem (interactions is
--      append-only, so a save followed by an unsave resolves to 'unsave' and
--      is dropped here). Keep only save / super_like / dislike.
--   2. If no remaining latest-action is save or super_like → cold start:
--      return `limit_in` random poems.
--   3. Otherwise compute a taste vector = SUM(weight * embedding) across the
--      filtered latest actions, with weights super_like=2.0, save=1.0,
--      dislike=-2.0. Cosine ordering is rank-invariant under positive scaling
--      so the un-normalized sum is equivalent to a weighted average here.
--   4. Return cosine-nearest poems the user has not yet interacted with.
--
-- Returns the same columns the swiper currently reads from poems:
--   id, title, author, body, line_count.
-- =============================================================================

create or replace function recommend_poems(user_id_in uuid, limit_in int)
returns table (
  id          text,
  title       text,
  author      text,
  body        text,
  line_count  integer
)
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  has_positive boolean;
  taste_vector vector(1536);
begin
  if auth.uid() is null then
    raise exception 'must be authenticated';
  end if;
  if auth.uid() <> user_id_in then
    raise exception 'user_id_in must match auth.uid()';
  end if;

  -- Warm vs cold via latest-action-per-poem.
  with latest_action as (
    select distinct on (poem_id) poem_id, action
    from interactions
    where user_id = user_id_in
    order by poem_id, created_at desc
  )
  select exists (
    select 1 from latest_action where action in ('save', 'super_like')
  )
  into has_positive;

  if not has_positive then
    return query
    select p.id, p.title, p.author, p.body, p.line_count
    from poems p
    order by random()
    limit limit_in;
    return;
  end if;

  with latest_action as (
    select distinct on (poem_id) poem_id, action
    from interactions
    where user_id = user_id_in
    order by poem_id, created_at desc
  )
  select sum(
    p.embedding * array_fill(
      (case la.action
         when 'super_like' then 2.0
         when 'save'       then 1.0
         when 'dislike'    then -2.0
       end)::real,
      array[1536]
    )::vector
  )
  into taste_vector
  from latest_action la
  join poems p on p.id = la.poem_id
  where la.action in ('save', 'super_like', 'dislike')
    and p.embedding is not null;

  -- All positive anchors were on un-embedded poems → degrade to cold start.
  if taste_vector is null then
    return query
    select p.id, p.title, p.author, p.body, p.line_count
    from poems p
    order by random()
    limit limit_in;
    return;
  end if;

  return query
  select p.id, p.title, p.author, p.body, p.line_count
  from poems p
  where p.embedding is not null
    and not exists (
      select 1 from interactions i
      where i.user_id = user_id_in and i.poem_id = p.id
    )
  order by p.embedding <=> taste_vector
  limit limit_in;
end;
$$;

grant execute on function recommend_poems(uuid, int) to authenticated;
