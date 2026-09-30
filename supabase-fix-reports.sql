-- ============================================================
--  FIX: make Report history load  (run in Supabase SQL Editor)
--  Safe to run even if you've run parts before.
--  (Requires supabase-roles.sql to have been run, for my_role().)
-- ============================================================

-- 1) Ensure the reports table exists.
create table if not exists public.reports (
  id          uuid        primary key default gen_random_uuid(),
  created_at  timestamptz not null default now(),
  created_by  uuid        default auth.uid() references auth.users(id) on delete set null
);

-- 2) Ensure every column the app reads is present.
alter table public.reports add column if not exists author      text;
alter table public.reports add column if not exists period_from text;
alter table public.reports add column if not exists period_to   text;
alter table public.reports add column if not exists model       text;
alter table public.reports add column if not exists content     text;

-- 3) Row level security + policies.
alter table public.reports enable row level security;

drop policy if exists "reports_select" on public.reports;
create policy "reports_select" on public.reports
  for select to authenticated using (true);

drop policy if exists "reports_insert" on public.reports;
create policy "reports_insert" on public.reports
  for insert to authenticated with check (public.my_role() in ('admin','viewer'));

drop policy if exists "reports_delete" on public.reports;
create policy "reports_delete" on public.reports
  for delete to authenticated using (public.my_role() = 'admin');
