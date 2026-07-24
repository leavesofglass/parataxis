-- =============================================================================
-- 0026 — Add body_html column to poems
-- =============================================================================
-- Stores poem body text with <em> emphasis and leading-space indentation
-- preserved from the original source HTML. NULL means no markup is available
-- for this poem and the plain body is canonical.
-- Only populated where body_html actually differs from body.
-- =============================================================================

alter table poems
  add column if not exists body_html text;
