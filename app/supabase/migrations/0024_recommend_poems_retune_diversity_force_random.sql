-- =============================================================================
-- 0024 — Recommender: retune constants, add diversity, add force_random
-- =============================================================================
-- Three changes bundled into a single migration:
--
-- 1. Retune constants toward more randomness (dial back once interaction data
--    accumulates — for now, better too random than too narrow):
--
--       MIN_SIGNALS      5   → 15
--       CANDIDATE_POOL   300 → 1000
--       EXPLORE_FRAC     0.28 → 0.5
--
-- 2. Diversity, applied to BOTH the taste slice AND the random / cold-start /
--    mix-it-up slice:
--       - at most one poem per author per batch
--       - spread across the corpus column (not proportional to corpus size —
--         the corpus is skewed, Verse Daily is over half — so weight toward
--         variety, not proportionality)
--       - new optional `recent_authors` parameter (last ~10 authors served,
--         excluded from the next batch); client passes it
--
-- 3. New `force_random` boolean — the "Mix it up" mode. Bypasses taste
--    ranking but still respects length buckets, already-seen exclusion, and
--    diversity constraints.
--
-- Because these constraints stack with the length buckets and already-seen
-- exclusion, they can empty the candidate pool. Rather than ever returning
-- zero rows, we relax them in a defined order inside the picker:
--       Level 0: one-per-author + exclude recent authors + corpus spread
--       Level 1: drop corpus spread
--       Level 2: also drop recent-authors exclusion
--       Level 3: also drop one-per-author (plain random from the pool)
--
-- Structure follows 0022: candidates are materialised into text[] arrays via
-- SELECT INTO before any RETURN QUERY. No vector-typed variables and no
-- variable LIMITs inside CTEs within a single RETURN QUERY.
--
-- Signature changes (two new params), so the previous overload is dropped
-- explicitly rather than relying on CREATE OR REPLACE.
-- =============================================================================

drop function if exists recommend_poems(uuid, int, boolean, boolean, boolean);

-- ── Internal helper: diverse selection from a materialised candidate pool ──
-- Given a text[] of candidate poem ids, picks up to `n` ids applying the
-- diversity constraints described above, relaxing them in order until it can
-- return `n` rows (or the pool itself is exhausted).
create or replace function _recommend_pick_diverse(
  cand_ids       text[],
  n              int,
  recent_authors text[]
)
returns text[]
language plpgsql
set search_path = public, extensions
as $$
declare
  recent text[] := array_remove(coalesce(recent_authors, '{}'::text[]), null);
  picked text[];
begin
  if cand_ids is null
     or coalesce(array_length(cand_ids, 1), 0) = 0
     or n <= 0 then
    return '{}'::text[];
  end if;

  -- Level 0: one-per-author + exclude recent authors + spread across corpus.
  select array_agg(sub.id)
  into picked
  from (
    select ranked.id
    from (
      select da.id, da.corpus,
             row_number() over (
               partition by coalesce(da.corpus, '__none__')
               order by random()
             ) as rn
      from (
        select distinct on (p.author) p.id, p.author, p.corpus
        from poems p
        where p.id = any(cand_ids)
          and p.author <> all(recent)
        order by p.author, random()
      ) da
    ) ranked
    order by ranked.rn, random()
    limit n
  ) sub;
  if coalesce(array_length(picked, 1), 0) >= n then
    return picked;
  end if;

  -- Level 1: drop corpus spread. Keep one-per-author + exclude recent.
  select array_agg(sub.id)
  into picked
  from (
    select distinct on (p.author) p.id
    from poems p
    where p.id = any(cand_ids)
      and p.author <> all(recent)
    order by p.author, random()
    limit n
  ) sub;
  if coalesce(array_length(picked, 1), 0) >= n then
    return picked;
  end if;

  -- Level 2: drop recent-authors exclusion. Keep one-per-author only.
  select array_agg(sub.id)
  into picked
  from (
    select distinct on (p.author) p.id
    from poems p
    where p.id = any(cand_ids)
    order by p.author, random()
    limit n
  ) sub;
  if coalesce(array_length(picked, 1), 0) >= n then
    return picked;
  end if;

  -- Level 3: drop all diversity. Plain random from the pool.
  select array_agg(sub.id)
  into picked
  from (
    select p.id
    from poems p
    where p.id = any(cand_ids)
    order by random()
    limit n
  ) sub;
  return coalesce(picked, '{}'::text[]);
end;
$$;

create function recommend_poems(
  user_id_in     uuid,
  limit_in       int,
  show_short     boolean default true,
  show_medium    boolean default true,
  show_long      boolean default true,
  recent_authors text[]  default null,
  force_random   boolean default false
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
  MIN_SIGNALS    constant int     := 15;
  CANDIDATE_POOL constant int     := 1000;
  EXPLORE_FRAC   constant numeric := 0.5;

  positive_count       int;
  taste_vector         vector(1536);
  explore_n            int;
  taste_n              int;
  cand_ids             text[];
  taste_picked         text[];
  taste_picked_authors text[];
  explore_pool_ids     text[];
  explore_picked       text[];
  random_pool_ids      text[];
  random_picked        text[];
begin
  if auth.uid() is null then
    raise exception 'must be authenticated';
  end if;
  if auth.uid() <> user_id_in then
    raise exception 'user_id_in must match auth.uid()';
  end if;

  if not force_random then
    select count(distinct poem_id)
    into positive_count
    from interactions
    where user_id = user_id_in
      and action in ('save', 'super_like', 'like', 'share');
  end if;

  -- ── Random branch: mix-it-up, cold-start, or all-zero taste fallback ────
  if force_random or positive_count < MIN_SIGNALS then
    select array_agg(sub.id)
    into random_pool_ids
    from (
      select p.id
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
      limit CANDIDATE_POOL
    ) sub;
    random_pool_ids := coalesce(random_pool_ids, '{}'::text[]);

    random_picked := _recommend_pick_diverse(random_pool_ids, limit_in, recent_authors);

    return query
    select p.id, p.title, p.author, p.body, p.line_count
    from unnest(random_picked) with ordinality as t(pid, ord)
    join poems p on p.id = t.pid
    order by t.ord;
    return;
  end if;

  -- ── Personalised branch: build the taste vector ─────────────────────────
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

  -- Fallback: signals cancelled to zero or all landed on un-embedded poems.
  if taste_vector is null then
    select array_agg(sub.id)
    into random_pool_ids
    from (
      select p.id
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
      limit CANDIDATE_POOL
    ) sub;
    random_pool_ids := coalesce(random_pool_ids, '{}'::text[]);

    random_picked := _recommend_pick_diverse(random_pool_ids, limit_in, recent_authors);

    return query
    select p.id, p.title, p.author, p.body, p.line_count
    from unnest(random_picked) with ordinality as t(pid, ord)
    join poems p on p.id = t.pid
    order by t.ord;
    return;
  end if;

  explore_n := greatest(1, round(limit_in * EXPLORE_FRAC)::int);
  taste_n   := limit_in - explore_n;

  -- Taste candidate pool: top CANDIDATE_POOL by cosine similarity.
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
  cand_ids := coalesce(cand_ids, '{}'::text[]);

  if taste_n > 0 then
    taste_picked := _recommend_pick_diverse(cand_ids, taste_n, recent_authors);
  else
    taste_picked := '{}'::text[];
  end if;

  -- Extend the recent-authors exclusion with authors just picked in the
  -- taste slice so "one per author per batch" holds across both slices.
  select array_agg(distinct p.author)
  into taste_picked_authors
  from poems p
  where p.id = any(taste_picked);
  taste_picked_authors := coalesce(taste_picked_authors, '{}'::text[]);

  -- Explore pool: unseen poems outside the taste candidate pool.
  select array_agg(sub.id)
  into explore_pool_ids
  from (
    select p.id
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
    and p.id <> all(cand_ids)
    order by random()
    limit CANDIDATE_POOL
  ) sub;
  explore_pool_ids := coalesce(explore_pool_ids, '{}'::text[]);

  explore_picked := _recommend_pick_diverse(
    explore_pool_ids,
    explore_n,
    array_remove(coalesce(recent_authors, '{}'::text[]), null) || taste_picked_authors
  );

  return query
  select p.id, p.title, p.author, p.body, p.line_count
  from unnest(taste_picked) with ordinality as t(pid, ord)
  join poems p on p.id = t.pid
  order by t.ord;

  return query
  select p.id, p.title, p.author, p.body, p.line_count
  from unnest(explore_picked) with ordinality as t(pid, ord)
  join poems p on p.id = t.pid
  order by t.ord;
end;
$$;

grant execute on function recommend_poems(uuid, int, boolean, boolean, boolean, text[], boolean) to authenticated;
