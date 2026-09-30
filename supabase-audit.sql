-- ============================================================
--  Audit log  (run AFTER supabase-roles.sql)
--  Records who created / edited / deleted observations.
-- ============================================================
create table if not exists public.audit (
  id         uuid        primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  actor      text,
  action     text,
  robot      text,
  obs_date   text
);

alter table public.audit enable row level security;

-- View: any signed-in user. Insert: any signed-in user (the app logs actions).
-- Delete: admin only.
drop policy if exists "audit_select" on public.audit;
create policy "audit_select" on public.audit for select to authenticated using (true);

drop policy if exists "audit_insert" on public.audit;
create policy "audit_insert" on public.audit for insert to authenticated with check (true);

drop policy if exists "audit_delete" on public.audit;
create policy "audit_delete" on public.audit for delete to authenticated using (public.my_role() = 'admin');
