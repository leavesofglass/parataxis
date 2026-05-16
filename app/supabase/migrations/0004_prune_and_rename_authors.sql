-- =============================================================================
-- parataxis — prune cut authors and normalise five canonical names
-- =============================================================================
-- Mirrors the JSON edits applied to data/corpus_30lines_clean.json:
--   • Removes all poems (and their interactions) for 6 cut authors
--   • Renames 5 surviving authors to their short canonical form
--
-- Safe to re-run: removes operate on the cut-list, renames are no-ops once
-- the new names are in place.
--
-- Ordering note: interactions are deleted before poems even though the FK in
-- 0001_initial_schema.sql declares ON DELETE CASCADE. Doing it explicitly
-- keeps the migration correct regardless of future FK changes.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 1) Delete interactions whose poem is being cut.
-- ---------------------------------------------------------------------------

delete from interactions
where poem_id in (
  select id from poems
  where author in (
    'Thomas Carew',
    'Gilbert Keith Chesterton',
    'John Clare',
    'Philip Sidney (Sir)',
    'Sir Philip Sidney',
    'John Wilmot',
    'Clark Ashton Smith'
  )
);


-- ---------------------------------------------------------------------------
-- 2) Delete the poems themselves.
-- ---------------------------------------------------------------------------

delete from poems
where author in (
  'Thomas Carew',
  'Gilbert Keith Chesterton',
  'John Clare',
  'Philip Sidney (Sir)',
  'Sir Philip Sidney',
  'John Wilmot',
  'Clark Ashton Smith'
);


-- ---------------------------------------------------------------------------
-- 3) Rename surviving authors to canonical short forms.
-- ---------------------------------------------------------------------------

update poems set author = 'A.E. Housman'
  where author = 'Alfred Edward Housman';

update poems set author = 'D.H. Lawrence'
  where author = 'D. H. Lawrence (David Herbert Richards)';

update poems set author = 'Fernando Pessoa'
  where author in (
    'Fernando Antônio Nogueira Pessoa',
    'Fernando Ant''nio Nogueira Pessoa'
  );

update poems set author = 'Petrarch'
  where author = 'Francesco Petrarca (Petrarch)';

update poems set author = 'Oscar Wilde'
  where author = 'Oscar Fingal O''Flahertie Wills Wilde';
