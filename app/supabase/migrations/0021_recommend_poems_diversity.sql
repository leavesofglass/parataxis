-- =============================================================================
-- 0021 — Recommender diversity: signal threshold, candidate sampling, exploration
-- =============================================================================
-- Three tunable constants at the top of the function body:
--
--   MIN_SIGNALS    int     — min positive interactions before personalising.
--                            Below this, serve random-within-buckets so a single
--                            liked poem can't collapse the whole feed.
--
--   CANDIDATE_POOL int     — once personalising, rank the corpus by cosine
--                            similarity and draw the taste batch from the top N
--                            rather than the strict top limit_in, so results
--                            don't cluster into one sub-genre.
--
--   EXPLORE_FRAC   numeric — share of each batch reserved for random exploration
--                            (bucket-filtered, unseen, outside the candidate pool).
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
  MIN_SIGNALS    constant int     := 5;    -- personalise only after this many positive signals
  CANDIDATE_POOL constant int     := 300;  -- top-N by similarity to randomly sample from
  EXPLORE_FRAC   constant numeric := 0.28; -- share of each batch that is random exploration

  positive_count int;
  taste_vector   vector(1536);
  explore_n      int;
  taste_n        int;
begin
  if auth.uid() is null then
    raise exception 'must be authenticated';
  end if;
  if auth.uid() <> user_id_in then
    raise exception 'user_id_in must match auth.uid()';
  end if;

  -- Count distinct positive signals (un-toggled actions count negatively but
  -- we only look at the positive side here for threshold purposes).
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

  -- Build taste vector from the weighted interaction history.
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

  -- Personalised path: blend a random draw from the top-CANDIDATE_POOL with
  -- random exploration outside that pool.
  explore_n := greatest(1, round(limit_in * EXPLORE_FRAC)::int);
  taste_n   := limit_in - explore_n;

  return query
  with candidates as (
    -- Top CANDIDATE_POOL unseen poems ranked by cosine similarity to taste vector.
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
    limit CANDIDATE_POOL
  ),
  taste_sample as (
    -- Randomly draw taste_n from the candidate pool.
    select * from candidates
    order by random()
    limit taste_n
  ),
  explore_sample as (
    -- Randomly draw explore_n from poems outside the candidate pool.
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
    and p.id not in (select id from candidates)
    order by random()
    limit explore_n
  )
  select * from taste_sample
  union all
  select * from explore_sample;
end;
$$;

grant execute on function recommend_poems(uuid, int, boolean, boolean, boolean) to authenticated;
