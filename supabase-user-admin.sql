-- ============================================================
--  In-app user management  (run AFTER supabase-roles.sql)
--  Lets admins list all users and change anyone's role from the app.
-- ============================================================

-- Admins can view every profile (others still see only their own).
drop policy if exists "profiles_select_admin" on public.profiles;
create policy "profiles_select_admin" on public.profiles
  for select to authenticated using (public.my_role() = 'admin');

-- Admins can update any profile (e.g. change a role).
drop policy if exists "profiles_update_admin" on public.profiles;
create policy "profiles_update_admin" on public.profiles
  for update to authenticated
  using (public.my_role() = 'admin')
  with check (public.my_role() = 'admin');
