-- =============================================================================
-- 0030 — recommend_poems corpus_filter (dev knob) + list_corpora helper
-- =============================================================================
-- Additive-only, mirrors the 0028 pattern.
--
--   recommend_poems(int, text[], boolean, boolean, boolean, text[], boolean)
--     New overload. Body is copied from the 0028 overload with one extra
--     predicate on each of the four candidate-pool queries so callers can
--     restrict which corpora are eligible.
--
--     corpus_filter is REQUIRED (no default) on this overload — Postgres
--     forbids a required param AFTER any defaulted param, so it sits in
--     position 2 (right after limit_in) rather than at the tail. Parameter
--     position doesn't matter for PostgREST dispatch: it resolves overloads
--     by the SET of parameter NAMES in the request body. Since the 0028
--     overload has no corpus_filter param, a request that includes
--     corpus_filter can only match this overload — and a request that omits
--     it can only match the 0028 overload. No ambiguity window during
--     rollout.
--
--     Semantics: corpus_filter = '{}'  → no restriction (all corpora eligible).
--                corpus_filter <> '{}' → whitelist of corpus values, plus the
--                                        sentinel '__null__' as an opt-in for
--                                        rows where poems.corpus IS NULL
--                                        (originals ingested pre-0018).
--
--   list_corpora() returns text[]
--     Helper for the dev-only account-page checkboxes. 0029 revoked direct
--     SELECT on poems, so the client can't run SELECT DISTINCT corpus itself.
--     Grant to authenticated only — anon has no reason to enumerate corpora.
--
-- This migration is intentionally additive. It does NOT drop the 0028
-- recommend_poems overload — that happens in 0031 after the client and the
-- warmup route are confirmed to be sending corpus_filter in production.
-- =============================================================================

create function recommend_poems(
  limit_in       int,
  corpus_filter  text[],
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
  line_count  integer,
  body_html   text
)
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  MIN_SIGNALS    constant int     := 15;
  CANDIDATE_POOL constant int     := 1000;
  EXPLORE_FRAC   constant numeric := 0.5;

  uid                  uuid := auth.uid();
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
  if uid is null then
    raise exception 'must be authenticated';
  end if;

  if not force_random then
    select count(distinct poem_id)
    into positive_count
    from interactions
    where user_id = uid
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
      and (
        coalesce(array_length(corpus_filter, 1), 0) = 0
        or p.corpus = any(corpus_filter)
        or (p.corpus is null and '__null__' = any(corpus_filter))
      )
      and not exists (
        select 1 from interactions i
        where i.user_id = uid and i.poem_id = p.id
      )
      order by random()
      limit CANDIDATE_POOL
    ) sub;
    random_pool_ids := coalesce(random_pool_ids, '{}'::text[]);

    random_picked := _recommend_pick_diverse(random_pool_ids, limit_in, recent_authors);

    return query
    select p.id, p.title, p.author, p.body, p.line_count, p.body_html
    from unnest(random_picked) with ordinality as t(pid, ord)
    join poems p on p.id = t.pid
    order by t.ord;
    return;
  end if;

  -- ── Personalised branch: build the taste vector ─────────────────────────
  with raw as (
    select poem_id, action, created_at
    from interactions
    where user_id = uid
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
      and (
        coalesce(array_length(corpus_filter, 1), 0) = 0
        or p.corpus = any(corpus_filter)
        or (p.corpus is null and '__null__' = any(corpus_filter))
      )
      and not exists (
        select 1 from interactions i
        where i.user_id = uid and i.poem_id = p.id
      )
      order by random()
      limit CANDIDATE_POOL
    ) sub;
    random_pool_ids := coalesce(random_pool_ids, '{}'::text[]);

    random_picked := _recommend_pick_diverse(random_pool_ids, limit_in, recent_authors);

    return query
    select p.id, p.title, p.author, p.body, p.line_count, p.body_html
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
      and (
        coalesce(array_length(corpus_filter, 1), 0) = 0
        or p.corpus = any(corpus_filter)
        or (p.corpus is null and '__null__' = any(corpus_filter))
      )
      and not exists (
        select 1 from interactions i
        where i.user_id = uid and i.poem_id = p.id
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

  select array_agg(distinct p.author)
  into taste_picked_authors
  from poems p
  where p.id = any(taste_picked);
  taste_picked_authors := coalesce(taste_picked_authors, '{}'::text[]);

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
    and (
      coalesce(array_length(corpus_filter, 1), 0) = 0
      or p.corpus = any(corpus_filter)
      or (p.corpus is null and '__null__' = any(corpus_filter))
    )
    and not exists (
      select 1 from interactions i
      where i.user_id = uid and i.poem_id = p.id
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
  select p.id, p.title, p.author, p.body, p.line_count, p.body_html
  from unnest(taste_picked) with ordinality as t(pid, ord)
  join poems p on p.id = t.pid
  order by t.ord;

  return query
  select p.id, p.title, p.author, p.body, p.line_count, p.body_html
  from unnest(explore_picked) with ordinality as t(pid, ord)
  join poems p on p.id = t.pid
  order by t.ord;
end;
$$;

grant execute on function recommend_poems(int, text[], boolean, boolean, boolean, text[], boolean)
  to anon, authenticated;


-- list_corpora returns every corpus value the dev checkboxes need to render,
-- including the '__null__' sentinel iff any null-corpus rows exist. Same
-- sentinel string that recommend_poems' WHERE clause matches on, so checkbox
-- and filter cannot disagree. Sentinel is appended explicitly rather than
-- sorted alphabetically so it lands at the end of the pill row (its label in
-- the UI is "originals").
create function list_corpora()
returns text[]
language sql
security definer
set search_path = public
as $$
  select coalesce(
           array_agg(distinct corpus order by corpus) filter (where corpus is not null),
           '{}'::text[]
         )
         || case
              when exists (select 1 from poems where corpus is null) then array['__null__']
              else '{}'::text[]
            end
  from poems
$$;

grant execute on function list_corpora() to authenticated;
