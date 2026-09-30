-- ============================================================
--  Supabase setup for the Robot Behavior QA tracker
--  Run this ONCE: Supabase dashboard -> SQL Editor -> New query
--  -> paste all of this -> Run.
-- ============================================================

-- One shared table. Each observation is one row; the whole entry is
-- stored as JSON so the app can evolve without schema changes.
create table if not exists public.observations (
  id         uuid        primary key default gen_random_uuid(),
  created_at timestamptz not null    default now(),
  created_by uuid        default auth.uid() references auth.users(id) on delete set null,
  entry      jsonb       not null
);

-- Turn on Row Level Security (this is what actually protects your data).
alter table public.observations enable row level security;

-- Shared team log: any SIGNED-IN user can read and write every row.
-- (Anonymous visitors get nothing.)
drop policy if exists "obs_select_authenticated" on public.observations;
create policy "obs_select_authenticated" on public.observations
  for select to authenticated using (true);

drop policy if exists "obs_insert_authenticated" on public.observations;
create policy "obs_insert_authenticated" on public.observations
  for insert to authenticated with check (true);

drop policy if exists "obs_update_authenticated" on public.observations;
create policy "obs_update_authenticated" on public.observations
  for update to authenticated using (true) with check (true);

drop policy if exists "obs_delete_authenticated" on public.observations;
create policy "obs_delete_authenticated" on public.observations
  for delete to authenticated using (true);


-- ============================================================
--  Profiles: tracks whether each user must still change the
--  default password you gave them. A trigger creates one row
--  per new user (defaulting to "must change = true").
-- ============================================================
create table if not exists public.profiles (
  id                   uuid        primary key references auth.users(id) on delete cascade,
  must_change_password boolean     not null default true,
  created_at           timestamptz not null default now()
);

alter table public.profiles enable row level security;

-- Each user can see and update only their own profile row.
drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own" on public.profiles
  for select to authenticated using (auth.uid() = id);

drop policy if exists "profiles_insert_own" on public.profiles;
create policy "profiles_insert_own" on public.profiles
  for insert to authenticated with check (auth.uid() = id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own" on public.profiles
  for update to authenticated using (auth.uid() = id) with check (auth.uid() = id);

-- Auto-create a profile (must_change_password = true) for every new user.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, must_change_password)
  values (new.id, true)
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
