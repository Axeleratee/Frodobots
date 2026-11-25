-- ============================================================
--  NO-DATA CHECKS
--  Supabase -> SQL Editor -> New query. Run the parts IN ORDER,
--  one at a time: paste a part, press Run, look at the result,
--  then go on to the next part.
--
--  Background: every log lives in observations.entry (JSON). A
--  no-data check is an entry whose entry.noData is true. The notes
--  are entry.notes - there is no separate notes column.
--
--  Nothing here deletes data. Part D undoes Part C.
-- ============================================================


-- ------------------------------------------------------------
-- PART A - add the is_no_data column (run once; safe to re-run)
--
-- A GENERATED column: Postgres fills it from the entry itself, so
-- it is always in step with what the app saves and can never drift.
-- The app does not write it. No RLS change is needed - policies are
-- per row, and this only adds a read-only column to each row.
-- ------------------------------------------------------------
alter table public.observations
  add column if not exists is_no_data boolean
  generated always as (
    coalesce(entry->>'noData', '') = 'true'
    or coalesce(entry->'issue' ? 'nodata', false)
  ) stored;

-- Check: how many entries are already no-data checks vs observations.
select is_no_data, count(*) from public.observations group by is_no_data order by is_no_data;


-- ------------------------------------------------------------
-- PART B - REVIEW ONLY. Lists entries whose notes say "no data"
-- (any capitalisation) but are not marked as no-data checks.
-- This changes nothing. Read through the list: if any row is a
-- real observation that just mentions "no data", note its id.
-- ------------------------------------------------------------
select
  id,
  entry->>'date'     as date,
  entry->>'robot'    as robot,
  entry->>'loggedBy' as logged_by,
  entry->>'notes'    as notes,
  entry->'issue'     as issue,
  created_at
from public.observations
where entry->>'notes' ilike '%no data%'
  and not is_no_data
order by entry->>'date', entry->>'robot';


-- ------------------------------------------------------------
-- PART C - MARK them as no-data checks.
-- Run only after reviewing Part B. It touches exactly the rows
-- Part B listed. To leave a row out, add its id to the list below
-- (uncomment the line and replace the example ids).
--
-- For each row it sets noData = true and issue = ["nodata"] (what
-- the app saves for a no-data check), and keeps the old issue in
-- entry.issue_before_backfill so Part D can put it back.
-- Notes, tasks and everything else stay as they are.
-- Note: changes made here do not appear in the app's Audit log.
-- ------------------------------------------------------------
update public.observations
set entry = entry || jsonb_build_object(
      'noData', true,
      'issue', jsonb_build_array('nodata'),
      'issue_before_backfill', coalesce(entry->'issue', 'null'::jsonb)
    )
where entry->>'notes' ilike '%no data%'
  and not is_no_data
  -- and id not in ('00000000-0000-0000-0000-000000000000', '11111111-1111-1111-1111-111111111111')
returning id, entry->>'date' as date, entry->>'robot' as robot, entry->>'notes' as notes;


-- ------------------------------------------------------------
-- PART D - UNDO (only if needed).
-- Puts back every row Part C changed. To undo just one row,
-- uncomment the last line and put its id in.
-- ------------------------------------------------------------
-- update public.observations
-- set entry = (entry - 'issue_before_backfill')
--             || jsonb_build_object('noData', false, 'issue', entry->'issue_before_backfill')
-- where entry ? 'issue_before_backfill'
--   -- and id = '00000000-0000-0000-0000-000000000000'
-- returning id, entry->>'date' as date, entry->>'robot' as robot;
