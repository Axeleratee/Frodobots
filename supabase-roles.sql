-- ============================================================
--  Roles & access control  (run AFTER supabase-setup.sql)
--  Supabase -> SQL Editor -> New query -> paste all -> Run.
-- ============================================================

-- 1) Add a role to each profile. Everyone starts as 'viewer' (least
--    privilege); you promote people to editor/admin yourself.
alter table public.profiles
  add column if not exists role text not null default 'viewer';

-- keep only valid values
alter table public.profiles drop constraint if exists profiles_role_check;
alter table public.profiles
  add constraint profiles_role_check check (role in ('admin','editor','viewer'));

-- 1b) Add an email column so you can tell which account each profile row is
--     (the id alone is just a UUID). Auto-filled below and by the trigger.
alter table public.profiles add column if not exists email text;
update public.profiles p
set email = u.email
from auth.users u
where u.id = p.id and p.email is null;

-- 2) New users are created as 'viewer' and must change their password.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, must_change_password, role)
  values (new.id, new.email, true, 'viewer')
  on conflict (id) do nothing;
  return new;
end;
$$;

-- 3) Helper: the caller's role (bypasses RLS so policies can use it safely).
create or replace function public.my_role()
returns text
language sql
stable
security definer
set search_path = public
as $$
  select role from public.profiles where id = auth.uid()
$$;

-- 4) Replace the observation policies with role-aware ones.
--    View: everyone signed in.  Add/Edit: admin or editor.  Delete: admin only.
drop policy if exists "obs_select_authenticated" on public.observations;
drop policy if exists "obs_insert_authenticated" on public.observations;
drop policy if exists "obs_update_authenticated" on public.observations;
drop policy if exists "obs_delete_authenticated" on public.observations;

create policy "obs_select" on public.observations
  for select to authenticated using (true);

create policy "obs_insert" on public.observations
  for insert to authenticated with check (public.my_role() in ('admin','editor'));

create policy "obs_update" on public.observations
  for update to authenticated
  using (public.my_role() in ('admin','editor'))
  with check (public.my_role() in ('admin','editor'));

create policy "obs_delete" on public.observations
  for delete to authenticated using (public.my_role() = 'admin');

-- 5) Make YOUR account an admin. Replace the email with your login email
--    (for a username "juan" with LOGIN_EMAIL_DOMAIN robotqa.local, that is
--    juan@robotqa.local). You can also do this in Table Editor -> profiles.
update public.profiles
set role = 'admin'
where id = (select id from auth.users where email = 'YOUR-ADMIN-EMAIL@robotqa.local');
