-- ============================================================
--  Customizable Task names & Issue types  (run AFTER supabase-roles.sql)
--  Lets admins add / edit / delete the options that appear in the
--  "Task" and "Issue type" pickers, without touching the code.
-- ============================================================

create table if not exists public.options (
  id          uuid        primary key default gen_random_uuid(),
  created_at  timestamptz not null default now(),
  kind        text        not null check (kind in ('task', 'issue')),
  key         text        not null,
  label       text        not null,
  severity    text,                       -- issues only: 'none' | 'minor' | 'major'
  sort_order  integer     not null default 0
);

-- One entry per key within a kind, so "edit" is an update and not a duplicate.
create unique index if not exists options_kind_key_idx on public.options (kind, key);

alter table public.options enable row level security;

-- Everyone signed in can READ the options (they fill the pickers).
drop policy if exists "options_select" on public.options;
create policy "options_select" on public.options
  for select to authenticated using (true);

-- Only admins may change them.
drop policy if exists "options_insert" on public.options;
create policy "options_insert" on public.options
  for insert to authenticated with check (public.my_role() = 'admin');

drop policy if exists "options_update" on public.options;
create policy "options_update" on public.options
  for update to authenticated using (public.my_role() = 'admin');

drop policy if exists "options_delete" on public.options;
create policy "options_delete" on public.options
  for delete to authenticated using (public.my_role() = 'admin');

-- ------------------------------------------------------------
-- Seed the table with the options the app shipped with, so nothing
-- disappears the first time you run this. Safe to re-run.
-- ------------------------------------------------------------
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
