-- =============================================================================
-- Preview: normalise corpus text — before/after for 10 poems
-- No writes. Prioritises poems with the acute-accent bug, then -- and quotes.
-- Review this before running 0023_normalize_corpus_text.sql.
-- =============================================================================
--
-- Transformation chain (applied in this order):
--   1. chr(180) [acute accent ´]   → chr(8217) [right single quote ']
--   2. '--'                         → chr(8212) [em dash —]
--   3. '"' after whitespace         → chr(8220) [left double quote "]
--   4. '"' at start of string       → chr(8220)
--   5. remaining '"'                → chr(8221) [right double quote "]
--   6. ''' after letter/digit       → chr(8217) [right single quote / apostrophe]
--   7. ''' before letter after \s   → chr(8216) [left single quote ']
--   8. ''' at start of string       → chr(8216)
--   9. remaining ''' (chr 39)       → chr(8217)
-- =============================================================================

with
-- Prioritise poems that have at least one affected character.
candidates as (
  select id, title, author, body
  from poems
  where position(chr(180) in body) > 0       -- acute accent (confirmed bug)
     or body like '%' || '--' || '%'          -- double hyphen
     or position('"'    in body) > 0          -- straight double quote
     or position(chr(39) in body) > 0         -- straight single quote / apostrophe
  order by
    (position(chr(180) in body) > 0) desc,   -- acute-accent poems first
    id
  limit 10
),
-- Step 1 & 2: punctuation substitutions (no regex needed)
s1 as (
  select id, title, author, body,
    replace(
      replace(body, chr(180), chr(8217)),     -- 1: acute accent → '
      '--', chr(8212)                          -- 2: double hyphen → em dash
    ) as b
  from candidates
),
-- Steps 3 & 4: opening double quotes
s2 as (
  select id, title, author, body,
    regexp_replace(
      regexp_replace(b, '(\s)"', '\1' || chr(8220), 'g'),  -- 3: after whitespace
      '^"', chr(8220)                                        -- 4: at start of string
    ) as b
  from s1
),
-- Step 5: remaining straight double quote → closing
s3 as (
  select id, title, author, body,
    replace(b, '"', chr(8221)) as b
  from s2
),
-- Step 6: straight apostrophe after letter/digit → right single quote
s4 as (
  select id, title, author, body,
    regexp_replace(b, '([[:alnum:]])''', '\1' || chr(8217), 'g') as b
  from s3
),
-- Steps 7 & 8: opening single quote (before alpha, after whitespace or at string start)
s5 as (
  select id, title, author, body,
    regexp_replace(
      regexp_replace(b, '(\s)''([[:alpha:]])', '\1' || chr(8216) || '\2', 'g'),  -- 7: after whitespace
      E'^''([[:alpha:]])', chr(8216) || '\1'                                       -- 8: at start
    ) as b
  from s4
),
-- Step 9: any remaining straight apostrophe → right single quote
s6 as (
  select id, title, author, body,
    replace(b, chr(39), chr(8217)) as b
  from s5
)
select
  id,
  title,
  author,
  body   as before_body,
  s6.b   as after_body
from s6
where body is distinct from s6.b;
