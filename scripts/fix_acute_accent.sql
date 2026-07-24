-- =============================================================================
-- Replace U+00B4 (acute accent ´) with U+2019 (right single quotation mark ')
-- in both poem body and title columns.
--
-- Returns one row: bodies_changed | titles_changed
-- Safe to re-run: subsequent passes touch 0 rows.
-- =============================================================================

with body_fixed as (
  update poems
  set body = replace(body, chr(180), chr(8217))
  where position(chr(180) in body) > 0
  returning id
),
title_fixed as (
  update poems
  set title = replace(title, chr(180), chr(8217))
  where position(chr(180) in title) > 0
  returning id
)
select
  (select count(*) from body_fixed)  as bodies_changed,
  (select count(*) from title_fixed) as titles_changed;
