-- =============================================================================
-- 0014_recommend_poems_length_filter
-- =============================================================================
-- Adds a third parameter `line_max_in int DEFAULT NULL` to recommend_poems.
-- When non-null, the candidate set is restricted to poems with
-- line_count <= line_max_in before random/cosine ordering. When NULL,
-- behaves identically to 0012.
--
-- Drop-then-create rather than CREATE OR REPLACE: PostgreSQL treats adding a
-- new parameter (even with DEFAULT) as a distinct overload, which would
-- leave the old 2-arg function in place and make 2-arg calls ambiguous.
-- =============================================================================

drop function if exists recommend_poems(uuid, int);

create or replace function recommend_poems(
  user_id_in   uuid,
  limit_in     int,
  line_max_in  int default null
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
    where (line_max_in is null or p.line_count <= line_max_in)
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

  if taste_vector is null then
    return query
    select p.id, p.title, p.author, p.body, p.line_count
    from poems p
    where (line_max_in is null or p.line_count <= line_max_in)
    order by random()
    limit limit_in;
    return;
  end if;

  return query
  select p.id, p.title, p.author, p.body, p.line_count
  from poems p
  where p.embedding is not null
    and (line_max_in is null or p.line_count <= line_max_in)
    and not exists (
      select 1 from interactions i
      where i.user_id = user_id_in and i.poem_id = p.id
    )
  order by p.embedding <=> taste_vector
  limit limit_in;
end;
$$;

grant execute on function recommend_poems(uuid, int, int) to authenticated;
