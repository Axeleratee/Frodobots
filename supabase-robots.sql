-- ============================================================
--  ROBOTS - manage the robot list from Settings
--  Supabase -> SQL Editor -> New query -> paste all of this -> Run.
--
--  Run AFTER supabase-team.sql (it needs the "options" table).
--  Safe to run more than once. Nothing below deletes data.
--
--  What this does:
--    1. lets the options table hold robots as well as tasks/issues
--    2. adds "retired_at", so a robot can be retired without
--       touching any of its past observations or assignments
--    3. adds the nine robots you already use, so nothing changes
--       until you add or retire one
--
--  Who can change the list: admins only (the existing options
--  policies already say so). Everyone signed in can read it.
-- ============================================================


-- 1) Allow kind = 'robot'.
--    The old check only allowed 'task' and 'issue'. Its name was chosen
--    by Postgres, so find it rather than guess it.
do $$
declare c record;
begin
  for c in
    select conname
    from pg_constraint
    where conrelid = 'public.options'::regclass
      and contype = 'c'
      and pg_get_constraintdef(oid) ilike '%kind%'
  loop
    execute format('alter table public.options drop constraint %I', c.conname);
  end loop;
end $$;

alter table public.options
  add constraint options_kind_check check (kind in ('task', 'issue', 'robot'));


-- 2) Retiring instead of deleting.
--    A retired robot leaves the pickers but keeps all of its history.
--    Restoring it is just clearing this column.
alter table public.options
  add column if not exists retired_at timestamptz;


-- 3) The robots in use today, in the order the app already shows them.
insert into public.options (kind, key, label, sort_order) values
  ('robot', 'Alpha',    'Alpha',    10),
  ('robot', 'Charlie',  'Charlie',  20),
  ('robot', 'Echo',     'Echo',     30),
  ('robot', 'Fox',      'Fox',      40),
  ('robot', 'Godzilla', 'Godzilla', 50),
  ('robot', 'Hugo',     'Hugo',     60),
  ('robot', 'Igor',     'Igor',     70),
  ('robot', 'Jackie',   'Jackie',   80),
  ('robot', 'Kilo',     'Kilo',     90)
on conflict (kind, key) do nothing;


-- Check: should list the nine robots, none retired.
select key as robot, retired_at
from public.options
where kind = 'robot'
order by sort_order, key;
