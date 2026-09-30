-- ============================================================
--  Report history  (run AFTER supabase-roles.sql)
--  Saves each generated AI report so the team can revisit them.
-- ============================================================
create table if not exists public.reports (
  id          uuid        primary key default gen_random_uuid(),
  created_at  timestamptz not null default now(),
  created_by  uuid        default auth.uid() references auth.users(id) on delete set null,
  author      text,
  period_from text,
  period_to   text,
  model       text,
  content     text        not null
);

alter table public.reports enable row level security;

-- View: any signed-in user. Create: admin or viewer (same as who may generate).
-- Delete: admin only.
drop policy if exists "reports_select" on public.reports;
create policy "reports_select" on public.reports
  for select to authenticated using (true);

drop policy if exists "reports_insert" on public.reports;
create policy "reports_insert" on public.reports
  for insert to authenticated with check (public.my_role() in ('admin','viewer'));

drop policy if exists "reports_delete" on public.reports;
create policy "reports_delete" on public.reports
  for delete to authenticated using (public.my_role() = 'admin');
