-- =============================================================================
-- 0012_dislike_weight_adjustment
-- =============================================================================
-- Softens the dislike penalty from -2.0 to -0.5 in recommend_poems. Skips are
-- now logged as dislikes, so the previous -2.0 would over-penalize the casual
-- "swipe past" gesture and pull the taste vector hard away from anything the
-- user merely declined to read. -0.5 keeps the negative signal directional
-- without overpowering save (1.0) / super_like (3.0).
--
-- Supersedes 0011 via CREATE OR REPLACE on the same signature. Function body,
-- guards, and search_path are otherwise identical to 0011.
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
         when 'super_like' then 3.0
         when 'save'       then 1.0
         when 'dislike'    then -0.5
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
