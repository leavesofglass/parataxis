-- =============================================================================
-- 0023 — Normalise corpus text: apostrophe fixes, em dashes, typographic quotes
-- =============================================================================
-- Transformation chain (same as corpus_preview_normalization.sql):
--   1. chr(180) [acute accent ´]   → chr(8217) [right single quote ']
--   2. '--'                         → chr(8212) [em dash —]
--   3. '"' after whitespace         → chr(8220) [left double quote "]
--   4. '"' at start of string       → chr(8220)
--   5. remaining '"'                → chr(8221) [right double quote "]
--   6. ''' after letter/digit       → chr(8217) [right single quote / apostrophe]
--   7. ''' before letter after \s   → chr(8216) [left single quote ']
--   8. ''' at start of string       → chr(8216)
--   9. remaining ''' (chr 39)       → chr(8217)
--
-- Only touches rows where the body actually changes.
-- Safe to re-run: subsequent passes are no-ops (no chr(39), chr(180), or "--" remain).
-- =============================================================================

with norm as (
  select
    id,
    -- 1 & 2: simple string replacements
    replace(
      replace(body, chr(180), chr(8217)),
      '--', chr(8212)
    ) as s1
  from poems
),
-- 3 & 4: opening double quote
n2 as (
  select id,
    regexp_replace(
      regexp_replace(s1, '(\s)"', '\1' || chr(8220), 'g'),
      '^"', chr(8220)
    ) as s2
  from norm
),
-- 5: remaining straight double quote → closing
n3 as (
  select id, replace(s2, '"', chr(8221)) as s3 from n2
),
-- 6: straight apostrophe after letter/digit → right single quote
n4 as (
  select id,
    regexp_replace(s3, '([[:alnum:]])''', '\1' || chr(8217), 'g') as s4
  from n3
),
-- 7 & 8: opening single quote before letter (after whitespace or at string start)
n5 as (
  select id,
    regexp_replace(
      regexp_replace(s4, '(\s)''([[:alpha:]])', '\1' || chr(8216) || '\2', 'g'),
      E'^''([[:alpha:]])', chr(8216) || '\1'
    ) as s5
  from n4
),
-- 9: remaining straight apostrophe → right single quote
n6 as (
  select id, replace(s5, chr(39), chr(8217)) as new_body from n5
)
update poems p
set body = n6.new_body
from n6
where p.id = n6.id
  and p.body is distinct from n6.new_body;
