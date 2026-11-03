-- ============================================================
--  TEAM MANAGEMENT  (run AFTER supabase-roles.sql)
--  Supabase -> SQL Editor -> New query -> paste all of this -> Run.
--
--  Safe to run more than once, and safe if you already ran
--  supabase-options.sql: that part is included here so you only
--  have to visit the SQL editor once. Nothing below deletes data.
--
--  What this adds:
--    1. options      - editable Task names & Issue types   (was pending)
--    2. assignments  - who is responsible for which robot
--    3. team_members() - lets non-admins see teammate names
-- ============================================================


-- ============================================================
--  1) OPTIONS - editable Task names & Issue types
--     (unchanged from supabase-options.sql; skipped if present)
-- ============================================================

create table if not exists public.options (
  id          uuid        primary key default gen_random_uuid(),
  created_at  timestamptz not null default now(),
  kind        text        not null check (kind in ('task', 'issue')),
  key         text        not null,
  label       text        not null,
  severity    text,
  sort_order  integer     not null default 0
);

create unique index if not exists options_kind_key_idx on public.options (kind, key);

alter table public.options enable row level security;

drop policy if exists "options_select" on public.options;
create policy "options_select" on public.options
  for select to authenticated using (true);

drop policy if exists "options_insert" on public.options;
create policy "options_insert" on public.options
  for insert to authenticated with check (public.my_role() = 'admin');

drop policy if exists "options_update" on public.options;
create policy "options_update" on public.options
  for update to authenticated using (public.my_role() = 'admin');

drop policy if exists "options_delete" on public.options;
create policy "options_delete" on public.options
  for delete to authenticated using (public.my_role() = 'admin');

insert into public.options (kind, key, label, severity, sort_order) values
  ('task','restocking fridge','restocking fridge',null,10),
  ('task','kitchen organization','kitchen organization',null,20),
  ('task','clothes washing','clothes washing',null,30),
  ('task','clean up the room','clean up the room',null,40),
  ('task','picking trash to rubbish bin','picking trash to rubbish bin',null,50),
  ('task','setting the table','setting the table',null,60),
  ('task','hang keys on a hook','hang keys on a hook',null,70),
  ('task','hang hanger','hang hanger',null,80),
  ('task','sweep floor','sweep floor',null,90),
  ('task','move the pillow to the sofa from floor','move the pillow to the sofa from floor',null,100),
  ('task','building children stool','building children stool',null,110),
  ('task','building children table','building children table',null,120),
  ('task','building plastic storage rack','building plastic storage rack',null,130),
  ('issue','none','No behavioral error observed','none',10),
  ('issue','idle_hand','Idle hand syndrome','major',20),
  ('issue','off_framing','Off framing','major',30),
  ('issue','improper_butler','Improper butler','major',40),
  ('issue','unnatural_pathing','Unnatural pathing','minor',50),
  ('issue','crab_walking','Crab walking','major',60),
  ('issue','foot_shuffling','Foot shuffling','minor',70),
  ('issue','camera_blur','Camera blur','major',80),
  ('issue','other','Other','minor',90)
on conflict (kind, key) do nothing;


-- ============================================================
--  2) ASSIGNMENTS - who is responsible for which robot
--
--  One row means: "this person is responsible for this robot,
--  from starts_on until ends_on (or until further notice)."
--
--  Deliberately NOT unique per (user, robot): overlapping rows
--  are allowed on purpose, so a robot can be handed over, shared
--  between two reviewers, or covered by a stand-in, without
--  having to delete history. Reassigning is adding a row, never
--  editing the past.
-- ============================================================

create table if not exists public.assignments (
  id          uuid        primary key default gen_random_uuid(),
  created_at  timestamptz not null default now(),
  created_by  uuid        default auth.uid() references auth.users(id) on delete set null,
  user_id     uuid        not null references auth.users(id) on delete cascade,
  robot       text        not null,
  starts_on   date        not null,
  ends_on     date,                       -- null = still theirs
  note        text,
  constraint assignments_dates_ok check (ends_on is null or ends_on >= starts_on)
);

-- "What is this person responsible for?" and "who covers this robot?"
create index if not exists assignments_user_idx  on public.assignments (user_id, starts_on);
create index if not exists assignments_robot_idx on public.assignments (robot, starts_on);

alter table public.assignments enable row level security;

-- Everyone signed in can SEE the roster. A reviewer needs to know what is
-- theirs, and seeing who covers the rest is how a team avoids double work.
drop policy if exists "assignments_select" on public.assignments;
create policy "assignments_select" on public.assignments
  for select to authenticated using (true);

-- Only admins decide who is responsible for what.
drop policy if exists "assignments_insert" on public.assignments;
create policy "assignments_insert" on public.assignments
  for insert to authenticated with check (public.my_role() = 'admin');

drop policy if exists "assignments_update" on public.assignments;
create policy "assignments_update" on public.assignments
  for update to authenticated
  using (public.my_role() = 'admin') with check (public.my_role() = 'admin');

drop policy if exists "assignments_delete" on public.assignments;
create policy "assignments_delete" on public.assignments
  for delete to authenticated using (public.my_role() = 'admin');


-- ============================================================
--  3) TEAM_MEMBERS() - teammate names for non-admins
--
--  Only admins may read public.profiles, so an editor currently
--  cannot resolve any name but their own - which would leave the
--  assignment board blank for them. This function exposes just
--  the three fields a roster needs, and nothing else: no email
--  address, no must_change_password, no other column that may be
--  added to profiles later.
-- ============================================================

create or replace function public.team_members()
returns table (id uuid, username text, role text)
language sql
security definer
set search_path = public
as $$
  select
    p.id,
    -- The app signs in as <username>@<domain>; show the username part.
    split_part(coalesce(p.email, ''), '@', 1) as username,
    p.role
  from public.profiles p
  where coalesce(p.email, '') <> ''
  order by 2;
$$;

revoke all on function public.team_members() from public;
grant execute on function public.team_members() to authenticated;


-- ============================================================
--  Done. Nothing was deleted, and no observation was touched.
--  Check it worked:
--     select * from public.team_members();
--     select count(*) from public.options;
--     select count(*) from public.assignments;   -- 0 is correct, it is new
-- ============================================================
