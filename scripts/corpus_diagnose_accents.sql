-- =============================================================================
-- Diagnostic: acute accent (U+00B4, chr(180)) in poem bodies
-- Run this first to confirm the scale and that every hit is a bad apostrophe.
-- =============================================================================

-- 1. How many poems are affected?
select count(*) as poems_with_acute_accent
from poems
where position(chr(180) in body) > 0;

-- 2. Five examples with up to 40 characters of context around each occurrence.
--    Each match is its own row; a poem with multiple hits appears multiple times.
select
  p.id,
  p.title,
  p.author,
  m.ctx as context
from poems p,
  lateral (
    select (regexp_matches(
              p.body,
              '.{0,40}' || chr(180) || '.{0,40}'
            ))[1] as ctx
  ) m
where position(chr(180) in p.body) > 0
order by p.id
limit 15;
