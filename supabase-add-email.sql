-- Run this if you already ran supabase-roles.sql and your profiles table has
-- no email column (so you can see which account each row belongs to).

alter table public.profiles add column if not exists email text;

update public.profiles p
set email = u.email
from auth.users u
where u.id = p.id and p.email is null;

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email, must_change_password, role)
  values (new.id, new.email, true, 'viewer')
  on conflict (id) do nothing;
  return new;
end;
$$;
