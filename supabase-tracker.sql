-- ============================================================
--  PROGRESS TRACKER  (run AFTER supabase-team.sql)
--  Supabase -> SQL Editor -> New query -> paste all -> Run.
--
--  Safe to run more than once. Creates one new table and touches
--  nothing that already exists - no observation, profile, option or
--  assignment is read, changed or deleted by this script.
-- ============================================================

-- One row = one review that someone is expected to finish:
-- "<reviewer> reviews <robot> for <date>, and it is <status>".
--
-- Status is set BY A PERSON and never inferred. Logging an observation
-- does not complete a task: a reviewer may log part of a day's work and
-- come back to it, so only they can say the review is finished.
create table if not exists public.review_tasks (
  id          uuid        primary key default gen_random_uuid(),
  created_at  timestamptz not null default now(),
  created_by  uuid        default auth.uid() references auth.users(id) on delete set null,

  obs_date    date        not null,
  robot       text        not null,
  reviewer_id uuid        references auth.users(id) on delete set null,

  status      text        not null default 'pending'
                          check (status in ('pending', 'in_progress', 'completed')),
  notes       text,

  -- Who last moved it, and when. Maintained by the trigger below so it
  -- cannot drift if a client forgets to send it.
  updated_at  timestamptz not null default now(),
  updated_by  uuid        default auth.uid() references auth.users(id) on delete set null,
  completed_at timestamptz
);

-- "The same assignment" is one reviewer, one robot, one date. Two
-- DIFFERENT reviewers splitting a robot for a day stays possible, which
-- is how a hand-over or a stand-in gets recorded.
create unique index if not exists review_tasks_unique_idx
  on public.review_tasks (obs_date, robot, reviewer_id);

-- A task with nobody assigned yet is still only allowed once per bot-day.
create unique index if not exists review_tasks_unassigned_idx
  on public.review_tasks (obs_date, robot)
  where reviewer_id is null;

create index if not exists review_tasks_date_idx     on public.review_tasks (obs_date desc);
create index if not exists review_tasks_reviewer_idx on public.review_tasks (reviewer_id, obs_date desc);
create index if not exists review_tasks_status_idx   on public.review_tasks (status);

-- ------------------------------------------------------------
--  Keep updated_at / updated_by / completed_at honest
-- ------------------------------------------------------------
create or replace function public.touch_review_task()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  new.updated_by := auth.uid();

  -- Stamp the moment it first reached "completed", and clear the stamp if
  -- it is reopened, so "completed today" means exactly that.
  if new.status = 'completed' and (tg_op = 'INSERT' or old.status is distinct from 'completed') then
    new.completed_at := now();
  elsif new.status <> 'completed' then
    new.completed_at := null;
  end if;

  return new;
end;
$$;

drop trigger if exists review_tasks_touch on public.review_tasks;
create trigger review_tasks_touch
  before insert or update on public.review_tasks
  for each row execute function public.touch_review_task();

-- ------------------------------------------------------------
--  Row level security
-- ------------------------------------------------------------
alter table public.review_tasks enable row level security;

-- The whole team sees the whole board. A tracker nobody can read is
-- useless, and knowing who holds what is how double work is avoided.
drop policy if exists "review_tasks_select" on public.review_tasks;
create policy "review_tasks_select" on public.review_tasks
  for select to authenticated using (true);

-- Admins hand work out.
drop policy if exists "review_tasks_insert" on public.review_tasks;
create policy "review_tasks_insert" on public.review_tasks
  for insert to authenticated with check (public.my_role() = 'admin');

-- An admin may change any task; a reviewer may move their OWN task along.
-- Reviewers cannot hand their work to someone else: the row must still be
-- theirs afterwards.
drop policy if exists "review_tasks_update" on public.review_tasks;
create policy "review_tasks_update" on public.review_tasks
  for update to authenticated
  using (
    public.my_role() = 'admin'
    or (public.my_role() = 'editor' and reviewer_id = auth.uid())
  )
  with check (
    public.my_role() = 'admin'
    or (public.my_role() = 'editor' and reviewer_id = auth.uid())
  );

drop policy if exists "review_tasks_delete" on public.review_tasks;
create policy "review_tasks_delete" on public.review_tasks
  for delete to authenticated using (public.my_role() = 'admin');

-- ============================================================
--  Done. Check it worked:
--     select count(*) from public.review_tasks;   -- 0 is correct, it is new
-- ============================================================
