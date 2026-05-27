-- =============================================================================
-- 0015_allow_delete_non_positive_interactions
-- =============================================================================
-- Adds a DELETE policy on interactions scoped to:
--   * the caller's own rows (auth.uid() = user_id), and
--   * "non-positive" actions: dislike, preview_open, preview_skip.
--
-- Required for the library's new Skipped section. The recommender excludes
-- any poem with any interaction row, so un-skipping a poem only resurfaces
-- it once every "non-decisive" interaction is cleared — the dislike row
-- plus any preview_* rows logged while the user was looking at it.
-- save / super_like / unsave rows remain immutable; they should only ever
-- be reversed by appending another append-only row (e.g. 'unsave').
-- =============================================================================

create policy "interactions: delete own non-positive"
  on interactions for delete
  using (
    auth.uid() = user_id
    and action in ('dislike', 'preview_open', 'preview_skip')
  );
