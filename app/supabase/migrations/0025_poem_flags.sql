create table poem_flags (
  id          uuid        primary key default gen_random_uuid(),
  poem_id     text        not null references poems(id) on delete cascade,
  reason      text        not null,
  note        text,
  user_id     uuid        not null references auth.users(id) on delete cascade,
  created_at  timestamptz not null default now()
);

alter table poem_flags enable row level security;

create policy "poem_flags: insert own"
  on poem_flags for insert
  with check (auth.uid() = user_id);
