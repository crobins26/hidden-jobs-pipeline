-- Career Intelligence Center v10 cloud schema
create table if not exists public.career_state (
  user_id uuid primary key references auth.users(id) on delete cascade,
  state jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.career_state enable row level security;

drop policy if exists "Users read own career state" on public.career_state;
create policy "Users read own career state"
on public.career_state for select
to authenticated
using ((select auth.uid()) = user_id);

drop policy if exists "Users insert own career state" on public.career_state;
create policy "Users insert own career state"
on public.career_state for insert
to authenticated
with check ((select auth.uid()) = user_id);

drop policy if exists "Users update own career state" on public.career_state;
create policy "Users update own career state"
on public.career_state for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create index if not exists career_state_updated_at_idx
on public.career_state(updated_at desc);
