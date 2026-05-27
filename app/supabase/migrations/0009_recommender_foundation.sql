-- =============================================================================
-- 0009_recommender_foundation
-- =============================================================================
-- Foundations for the recommendation pipeline:
--   1. Adds 'dislike' to the interaction_action enum (after 'unsave').
--   2. Builds an HNSW index over poems.embedding for cosine-similarity search.
-- =============================================================================

alter type interaction_action add value 'dislike' after 'unsave';

create index poems_embedding_hnsw
  on poems using hnsw (embedding vector_cosine_ops);
