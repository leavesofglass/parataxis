-- =============================================================================
-- parataxis — initial schema
-- =============================================================================
-- Tables:    profiles, poems, interactions
-- Extras:    pgvector extension, interaction_action enum,
--            auto-profile trigger, RLS policies
-- =============================================================================


-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------

create extension if not exists vector;


-- ---------------------------------------------------------------------------
-- Enum types
-- ---------------------------------------------------------------------------

create type interaction_action as enum (
  'preview_skip',   -- user swiped past without opening
  'preview_open',   -- user opened the full poem
  'save',           -- user saved to library
  'super_like',     -- user super-liked
  'unsave'          -- user removed from library
);


-- ---------------------------------------------------------------------------
-- profiles
-- mirrors auth.users 1-to-1; created automatically via trigger below
-- ---------------------------------------------------------------------------

create table profiles (
  id            uuid        primary key references auth.users(id) on delete cascade,
  display_name  text,
  is_anonymous  boolean     not null default true,
  created_at    timestamptz not null default now()
);


-- ---------------------------------------------------------------------------
-- poems
-- loaded from corpus_30lines_clean.json via service-role ingest script
-- embedding column reserved for future recommendation features
-- ---------------------------------------------------------------------------

create table poems (
  id          text     primary key,           -- "poem_0001" … "poem_0599"
  title       text     not null,
  author      text     not null,
  body        text     not null,              -- full poem text
  line_count  integer  not null,
  embedding   vector(1536)                    -- nullable; populated separately
);


-- ---------------------------------------------------------------------------
-- interactions
-- one row per user action on a poem; append-only by policy
-- ---------------------------------------------------------------------------

create table interactions (
  id          uuid                primary key default gen_random_uuid(),
  user_id     uuid                not null references auth.users(id) on delete cascade,
  poem_id     text                not null references poems(id) on delete cascade,
  action      interaction_action  not null,
  created_at  timestamptz         not null default now()
);


-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

-- library queries: "show me this user's saves, newest first"
create index interactions_user_created_at_idx
  on interactions (user_id, created_at desc);

-- dedup / seen-poem check: "has this user already acted on this poem?"
create index interactions_user_poem_idx
  on interactions (user_id, poem_id);

-- analytics: "how many interactions has this poem received?"
create index interactions_poem_idx
  on interactions (poem_id);


-- ---------------------------------------------------------------------------
-- Trigger: auto-create a profile row for every new auth user
-- Fires on INSERT into auth.users, including anonymous sign-ins
-- ---------------------------------------------------------------------------

create or replace function handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, is_anonymous)
  values (new.id, true);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure handle_new_user();


-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------

alter table profiles     enable row level security;
alter table poems        enable row level security;
alter table interactions enable row level security;


-- profiles: each user sees and edits only their own row
create policy "profiles: select own"
  on profiles for select
  using (auth.uid() = id);

create policy "profiles: update own"
  on profiles for update
  using (auth.uid() = id);


-- poems: any authenticated user can read; writes go through service role only
create policy "poems: authenticated read"
  on poems for select
  to authenticated
  using (true);


-- interactions: users can read and append their own rows; no edit or delete
create policy "interactions: select own"
  on interactions for select
  using (auth.uid() = user_id);

create policy "interactions: insert own"
  on interactions for insert
  with check (auth.uid() = user_id);
