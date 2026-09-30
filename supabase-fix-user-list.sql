-- ============================================================
--  FIX: make the User Management list show all users
--  Run in Supabase -> SQL Editor -> New query -> paste -> Run.
--  Safe to run even if you've already run parts of it.
--  (Requires supabase-roles.sql to have been run, for my_role().)
-- ============================================================

-- 1) Ensure the email column exists and is filled, so the list can show names.
alter table public.profiles add column if not exists email text;

update public.profiles p
set email = u.email
from auth.users u
where u.id = p.id and p.email is null;

-- 2) New users get their email + a default role automatically.
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

-- 3) Let ADMINS see and update EVERY profile (this is what makes the list appear).
drop policy if exists "profiles_select_admin" on public.profiles;
create policy "profiles_select_admin" on public.profiles
  for select to authenticated using (public.my_role() = 'admin');

drop policy if exists "profiles_update_admin" on public.profiles;
create policy "profiles_update_admin" on public.profiles
  for update to authenticated
  using (public.my_role() = 'admin')
  with check (public.my_role() = 'admin');
