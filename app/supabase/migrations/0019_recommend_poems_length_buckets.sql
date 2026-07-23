-- =============================================================================
-- 0019 — Replace line_max cap with three independent length buckets
-- =============================================================================
-- New parameters replace `line_max_in int`:
--   show_short   boolean DEFAULT true   → line_count <= 14
--   show_medium  boolean DEFAULT true   → line_count 15–40
--   show_long    boolean DEFAULT true   → line_count >= 41
--
-- All three on = no filter (any poem passes).
-- All three off = no poems returned (caller should prevent this in the UI).
-- =============================================================================

drop function if exists recommend_poems(uuid, int, int);

create or replace function recommend_poems(
  user_id_in   uuid,
  limit_in     int,
  show_short   boolean default true,
  show_medium  boolean default true,
  show_long    boolean default true
)
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

  select exists (
    select 1 from interactions
    where user_id = user_id_in
      and action in ('save', 'super_like', 'like', 'share')
  ) into has_positive;

  if not has_positive then
    return query
    select p.id, p.title, p.author, p.body, p.line_count
    from poems p
    where (
      (show_short  and p.line_count <= 14) or
      (show_medium and p.line_count between 15 and 40) or
      (show_long   and p.line_count >= 41)
    )
    order by random()
    limit limit_in;
    return;
  end if;

  with raw as (
    select poem_id, action, created_at
    from interactions
    where user_id = user_id_in
  ),
  poem_ids as (
    select distinct poem_id from raw
  ),
  latest_save as (
    select distinct on (poem_id) poem_id, action
    from raw
    where action in ('save', 'unsave', 'super_like')
    order by poem_id, created_at desc
  ),
  latest_like as (
    select distinct on (poem_id) poem_id, action
    from raw
    where action in ('like', 'unlike')
    order by poem_id, created_at desc
  ),
  latest_dislike as (
    select distinct on (poem_id) poem_id, action
    from raw
    where action in ('dislike', 'undislike')
    order by poem_id, created_at desc
  ),
  has_share as (
    select distinct poem_id from raw where action = 'share'
  ),
  poem_weight as (
    select
      pi.poem_id,
      case
        when coalesce(ld.action = 'dislike', false) then -0.5
        else greatest(
          case when coalesce(ls.action in ('save', 'super_like'), false) then 1.0 else 0.0 end,
          case when hs.poem_id is not null then 1.0 else 0.0 end,
          case when coalesce(ll.action = 'like', false) then 0.5 else 0.0 end
        )
      end::real as weight
    from poem_ids pi
    left join latest_save ls on ls.poem_id = pi.poem_id
    left join latest_like ll on ll.poem_id = pi.poem_id
    left join latest_dislike ld on ld.poem_id = pi.poem_id
    left join has_share hs on hs.poem_id = pi.poem_id
  )
  select sum(p.embedding * array_fill(pw.weight, array[1536])::vector)
  into taste_vector
  from poem_weight pw
  join poems p on p.id = pw.poem_id
  where pw.weight <> 0
    and p.embedding is not null;

  if taste_vector is null then
    return query
    select p.id, p.title, p.author, p.body, p.line_count
    from poems p
    where (
      (show_short  and p.line_count <= 14) or
      (show_medium and p.line_count between 15 and 40) or
      (show_long   and p.line_count >= 41)
    )
    order by random()
    limit limit_in;
    return;
  end if;

  return query
  select p.id, p.title, p.author, p.body, p.line_count
  from poems p
  where p.embedding is not null
    and (
      (show_short  and p.line_count <= 14) or
      (show_medium and p.line_count between 15 and 40) or
      (show_long   and p.line_count >= 41)
    )
    and not exists (
      select 1 from interactions i
      where i.user_id = user_id_in and i.poem_id = p.id
    )
  order by p.embedding <=> taste_vector
  limit limit_in;
end;
$$;

grant execute on function recommend_poems(uuid, int, boolean, boolean, boolean) to authenticated;
