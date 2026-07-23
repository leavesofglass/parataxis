-- =============================================================================
-- 0022 — Fix taste branch: materialise candidates before sampling
-- =============================================================================
-- Migration 0021 put `taste_vector` (a vector type) and integer variables
-- into LIMIT clauses inside CTEs within a single RETURN QUERY statement.
-- That pattern breaks at runtime even though the function compiles; the plan
-- cache for CTEs within RETURN QUERY handles user-defined-type parameters
-- differently from the simple top-level RETURN QUERY that worked in 0019.
--
-- Fix: materialise the candidate IDs into a text[] array in a separate INTO
-- query (same simple pattern as 0019's ORDER BY embedding <=> taste_vector),
-- then issue two ordinary RETURN QUERY statements that use = any() / != all()
-- on the array — no CTEs, no variable LIMITs inside a single complex query.
-- =============================================================================

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
  MIN_SIGNALS    constant int     := 5;    -- personalise only after this many distinct liked/saved poems
  CANDIDATE_POOL constant int     := 300;  -- top-N by cosine similarity to sample from
  EXPLORE_FRAC   constant numeric := 0.28; -- share of each batch that is random exploration

  positive_count int;
  taste_vector   vector(1536);
  explore_n      int;
  taste_n        int;
  cand_ids       text[];
begin
  if auth.uid() is null then
    raise exception 'must be authenticated';
  end if;
  if auth.uid() <> user_id_in then
    raise exception 'user_id_in must match auth.uid()';
  end if;

  -- Count distinct poems with at least one positive signal.
  select count(distinct poem_id)
  into positive_count
  from interactions
  where user_id = user_id_in
    and action in ('save', 'super_like', 'like', 'share');

  -- Cold-start: below threshold → random within buckets, excluding already-seen.
  if positive_count < MIN_SIGNALS then
    return query
    select p.id, p.title, p.author, p.body, p.line_count
    from poems p
    where (
      (show_short  and p.line_count <= 14) or
      (show_medium and p.line_count between 15 and 40) or
      (show_long   and p.line_count >= 41)
    )
    and not exists (
      select 1 from interactions i
      where i.user_id = user_id_in and i.poem_id = p.id
    )
    order by random()
    limit limit_in;
    return;
  end if;

  -- Build taste vector from weighted interaction history.
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

  -- Fallback: all signals were on un-embedded poems, or cancelled to zero → random.
  if taste_vector is null then
    return query
    select p.id, p.title, p.author, p.body, p.line_count
    from poems p
    where (
      (show_short  and p.line_count <= 14) or
      (show_medium and p.line_count between 15 and 40) or
      (show_long   and p.line_count >= 41)
    )
    and not exists (
      select 1 from interactions i
      where i.user_id = user_id_in and i.poem_id = p.id
    )
    order by random()
    limit limit_in;
    return;
  end if;

  -- Compute batch split.
  explore_n := greatest(1, round(limit_in * EXPLORE_FRAC)::int);
  taste_n   := limit_in - explore_n;

  -- Materialise the candidate pool: top CANDIDATE_POOL poems by cosine similarity.
  -- Kept as a separate INTO query (same pattern as 0019's working RETURN QUERY)
  -- to avoid putting a vector parameter and int variables inside CTE LIMIT clauses
  -- within a single RETURN QUERY statement, which fails at runtime.
  select array_agg(sub.id)
  into cand_ids
  from (
    select p.id
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
    limit CANDIDATE_POOL
  ) sub;

  -- Treat null (no candidates) as an empty array so the array operators below work.
  cand_ids := coalesce(cand_ids, '{}'::text[]);

  -- Taste slice: random draw from the candidate pool.
  if taste_n > 0 then
    return query
    select p.id, p.title, p.author, p.body, p.line_count
    from poems p
    where p.id = any(cand_ids)
    order by random()
    limit taste_n;
  end if;

  -- Explore slice: random poems outside the candidate pool, also unseen.
  return query
  select p.id, p.title, p.author, p.body, p.line_count
  from poems p
  where (
    (show_short  and p.line_count <= 14) or
    (show_medium and p.line_count between 15 and 40) or
    (show_long   and p.line_count >= 41)
  )
  and not exists (
    select 1 from interactions i
    where i.user_id = user_id_in and i.poem_id = p.id
  )
  and p.id != all(cand_ids)
  order by random()
  limit explore_n;
end;
$$;

grant execute on function recommend_poems(uuid, int, boolean, boolean, boolean) to authenticated;
