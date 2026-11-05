-- ============================================================
--  LATE UPLOAD BACKLOG  (run AFTER supabase-team.sql)
--  Supabase -> SQL Editor -> New query -> paste all -> Run.
--
--  Safe to run more than once. Creates one new table and touches
--  nothing that already exists - no observation, profile, option or
--  assignment is read, changed or deleted by this script.
-- ============================================================

-- The backlog LIST needs no table: it is every observation already
-- flagged as a late upload, so it collects itself and can never drift
-- out of step with the logs, or hold a duplicate.
--
-- What does need storing is the one thing nobody can derive: whether a
-- human has dealt with it. This table records that as EVENTS rather
-- than as a column, so the history is kept by construction - resolving
-- and reopening both leave a row behind, with who did it and when.
--
-- An entry's current status is simply its newest event; an observation
-- with no events at all is Unresolved.
create table if not exists public.late_backlog_events (
  id             uuid        primary key default gen_random_uuid(),
  created_at     timestamptz not null default now(),
  created_by     uuid        default auth.uid() references auth.users(id) on delete set null,

  observation_id uuid        not null references public.observations(id) on delete cascade,
  status         text        not null check (status in ('unresolved', 'resolved')),
  note           text
);

-- "What is the newest event for this observation?" is the only read.
create index if not exists late_backlog_obs_idx
  on public.late_backlog_events (observation_id, created_at desc);

alter table public.late_backlog_events enable row level security;

-- The whole team sees the backlog. Hiding it from the people who log the
-- observations would defeat the point of collecting them.
drop policy if exists "late_backlog_select" on public.late_backlog_events;
create policy "late_backlog_select" on public.late_backlog_events
  for select to authenticated using (true);

-- Admins and editors may resolve or reopen. Viewers cannot.
drop policy if exists "late_backlog_insert" on public.late_backlog_events;
create policy "late_backlog_insert" on public.late_backlog_events
  for insert to authenticated
  with check (public.my_role() in ('admin', 'editor'));

-- Deliberately NO update policy: an event is a record of something that
-- happened, and rewriting history is exactly what this table exists to
-- prevent. Changing your mind means adding another event.

-- Only an admin can remove an event, and only to undo a mistake.
drop policy if exists "late_backlog_delete" on public.late_backlog_events;
create policy "late_backlog_delete" on public.late_backlog_events
  for delete to authenticated using (public.my_role() = 'admin');

-- ============================================================
--  Done. Check it worked:
--     select count(*) from public.late_backlog_events;   -- 0 is correct, it is new
-- ============================================================
