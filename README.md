# Robot Behavior QA Tracker — shared database + AI reports

A single-page tracker with:
- **Supabase** for login (email + password) and a **shared team database**.
- One **Netlify function** that generates the report with **OpenAI** (your API
  key stays server-side).

```
Browser (index.html)
   |--> Supabase         (login + shared observations database)
   \--> Netlify Function --> OpenAI   (writes the report; verifies your login)
```

## What's in this folder

```
index.html                               the app
netlify.toml                             Netlify config (no build step)
netlify/functions/generate-report.mjs    the OpenAI proxy + editable prompt
supabase-setup.sql                       run once in Supabase to create the table
README.md                                this file
```

---

## Part A - Supabase (database + login)

### A1. Open your project
Go to supabase.com, open your project (or create one - the free tier is enough).

### A2. Create the table
Left sidebar -> SQL Editor -> New query -> paste the entire contents of
`supabase-setup.sql` -> Run. You should see "Success". This creates the shared
`observations` table with the right security rules.

### A3. Get your two public values
Left sidebar -> Project Settings -> API (or the "Connect" button up top). Copy:
- Project URL (looks like https://abcd1234.supabase.co)
- the publishable key (sb_publishable_...) - or, on older projects, the anon key.

These two are safe to put in the app; your data is protected by login + the
rules from A2, not by hiding them.

### A4. Paste them into the app
Open index.html, find the SUPABASE CONFIG block near the top of the <script>,
and replace the placeholders:

    const SUPABASE_URL = 'https://YOUR-PROJECT.supabase.co';
    const SUPABASE_ANON_KEY = 'YOUR-PUBLISHABLE-OR-ANON-KEY';
    const LOGIN_EMAIL_DOMAIN = 'robotqa.local';

LOGIN_EMAIL_DOMAIN: users sign in with a plain USERNAME. The app turns a
username into <username>@LOGIN_EMAIL_DOMAIN and uses that as the Supabase email.
Pick any domain-looking value (it does not need to be a real domain) and use the
SAME value when you create users in A5.

### A5. Accounts (only YOU create them - there is no self sign-up)
The app has no "Register" screen. You create each account, hand out a username +
a default password, and the user is forced to set their own password the first
time they log in.

1. Supabase -> Authentication -> Providers -> Email: turn "Confirm email" OFF
   (the usernames are not real inboxes, so confirmation must be off).
2. For each teammate: Supabase -> Authentication -> Users -> Add user. Enter:
   - Email: <username>@robotqa.local  (use the SAME domain as LOGIN_EMAIL_DOMAIN;
     for a user "juan" that is juan@robotqa.local)
   - Password: a default password you will give them
   - Tick "Auto Confirm User".
3. Tell the person their username (e.g. "juan") and the default password.

On their first login they must set a new password before the app opens. This is
enforced by the profiles table + trigger from supabase-setup.sql (make sure you
ran the WHOLE file, including the profiles part at the bottom).

---

## Part B - Netlify (hosting the app)

### B1. Deploy the folder
Netlify -> Add new site -> Deploy manually -> drag this whole folder in. Or use
Git / the Netlify CLI. Netlify just serves the static app (index.html).

### B2. Environment variables
None required on Netlify anymore. The AI report now runs on Supabase (Part C),
so the OpenAI key lives there, not here. (You can delete OPENAI_API_KEY from
Netlify if you had set it. The unused netlify/functions folder can stay; it does
no harm.)

---

## Part C - AI report on Supabase (Edge Function)

The report generator was moved from Netlify to a Supabase Edge Function so the
OpenAI call is NOT limited by Netlify's ~10 second timeout (that was the cause of
the "server error 502"). Edge Functions allow much longer execution, so long,
detailed reports finish fine.

The function lives in this folder at:
    supabase/functions/generate-report/index.ts

### C1. Install the Supabase CLI (one time)
- macOS:      brew install supabase/tap/supabase
- Windows:    scoop install supabase   (or see supabase.com/docs/guides/cli)
- npm (any):  npm install -g supabase
Check it works:  supabase --version

### C2. Log in and link your project
    supabase login
    supabase link --project-ref YOUR_PROJECT_REF
(YOUR_PROJECT_REF is the part of your URL: https://<REF>.supabase.co. You can
also copy it from Supabase -> Project Settings -> General.)
Run these from INSIDE this folder (the one that contains the "supabase" folder).

### C3. Set the OpenAI key as a secret (server-side, never in the browser)
    supabase secrets set OPENAI_API_KEY=sk-your-key
    # optional - choose a model (defaults to gpt-5.4-mini):
    supabase secrets set OPENAI_MODEL=gpt-5.4-mini
You do NOT need to set SUPABASE_URL or SUPABASE_ANON_KEY - Supabase injects those
into the function automatically.

### C4. Deploy the function
    supabase functions deploy generate-report --no-verify-jwt
(The function verifies the user's login itself, and --no-verify-jwt lets the
browser's preflight/CORS work. This is intentional and safe.)

### C5. Done
The app already knows the URL - it calls
<your-project-url>/functions/v1/generate-report automatically, sending the
logged-in user's token. Generate a report to test.

To change the model later:  supabase secrets set OPENAI_MODEL=<model>  (no
redeploy needed). To edit the prompt: edit the EDIT ZONE at the top of
supabase/functions/generate-report/index.ts, then re-run C4.
If a report fails, see the logs:  supabase functions logs generate-report

---

## Part D - Roles & access control

Three roles control what each person can do (see roles-and-access-strategy.md):
- Admin  - everything, incl. delete and generating AI reports.
- Editor - can log and edit observations, but NOT delete and NOT generate AI
           reports (to avoid cost).
- Viewer - can view everything and generate AI reports, but cannot add/edit/delete.

Enforcement is in TWO layers: the database (Supabase RLS - the real lock) and the
app UI (hides buttons a role can't use). The AI report function also checks the
role, so Editors can't generate reports even by calling it directly.

### D1. Run the roles SQL (once)
Supabase -> SQL Editor -> New query -> paste all of supabase-roles.sql -> Run.
Before running, edit the LAST line and put YOUR login email
(e.g. juan@robotqa.local) so your own account becomes 'admin'.
(Run supabase-setup.sql first if you haven't - roles.sql builds on it.)

### D2. Assign roles to people
New accounts default to 'viewer'. To change someone's role: Supabase -> Table
Editor -> profiles -> pick their row -> set role to admin / editor / viewer.

### D3. Re-deploy the report function
So the role check takes effect, redeploy the Edge Function (Part C) after paste-
updating it, or if you edit in the dashboard, just paste the latest
edge-generate-report.ts and Deploy again.

---

## Part E - Report history

Generated AI reports are saved so the team can revisit them (no need to
regenerate, which also saves OpenAI cost). They appear in a "Report history" card
under the Weekly report.

Run once: Supabase -> SQL Editor -> paste supabase-reports.sql -> Run.
(Run it AFTER supabase-roles.sql - it uses the my_role() helper.)

Who can do what with history: everyone signed in can VIEW past reports; Admin and
Viewer create them (by generating); only Admin can delete a saved report.

---

## Part F - In-app user management (admin)

Admins get a "User management" card on the Dashboard that lists all users (name,
email, role) and lets you change anyone's role from a dropdown. Your own role is
locked so you can't accidentally remove your own admin access.

Run once: Supabase -> SQL Editor -> paste supabase-user-admin.sql -> Run. (After
supabase-roles.sql - it uses the my_role() helper.)

### Full user admin (create / reset password / delete)
Admins can create accounts, reset passwords, and delete users from the User
Management tab once you deploy a second Edge Function (same steps as the report
one):

1. Supabase -> Edge Functions -> Deploy a new function -> Via Editor.
2. Name it EXACTLY: admin-users
3. Paste the contents of supabase/functions/admin-users/index.ts and turn OFF
   "Verify JWT".
4. Deploy. No secrets needed - the service-role key is auto-provided.

The function verifies the caller is an admin before doing anything and uses the
privileged service-role key server-side (never in the browser). New accounts are
created already-confirmed and must set their own password on first login; a
password reset forces the same.

---

## Task names, issue types, late uploads and the date overview

- Run `supabase-options.sql` once in the Supabase SQL editor to enable
  editing of the Task and Issue type lists. Until you do, the app keeps
  using its built-in lists and shows a note in Settings.
- Settings -> "Task names & issue types" (admins only): add, rename and
  remove options, and set Minor/Major severity for issue types. Removing
  an option never changes past observations - it only stops appearing in
  the picker.
- The log form has a "Late upload" checkbox. Late entries get a badge in
  the Logs and Recent tables, and the Logs tab has a late/on-time filter.
- The Logs tab starts with a "Date overview": one row per date showing
  Reviewed / No data / Late upload counts, with filters for dates that
  need action. Click a date to filter the log table to it.

## Navigation

The app has five tabs: Dashboard, Logs, Reporting, User Management, and Settings.
- Logs - the full observations table with filters (date range, logger, robot,
  task, issue, and text search) plus a "By" column showing who logged each row,
  and an Audit log beneath it showing who created / edited / deleted observations.
  The date and logger filters apply to the audit log too. Run supabase-audit.sql
  once to enable the audit log.
- Dashboard - quick data entry (Log an observation) and recent activity.
- Dashboard - quick data entry (Log an observation) and recent activity, with a
  "View all" link to the full observations table.
- Reporting - the AI/weekly report, the bot progression report, and Report
  history, all in one place so you can generate and review without leaving.
- User Management - admin only; assign roles (see Part F).
- Settings - your account and sign out (more coming later).
Editors don't see the AI report card; Viewers don't see the log form; only admins
see the User Management tab.

---

## Using it

1. Open your Netlify URL. You'll get a Sign in screen (no self sign-up).
2. Sign in with the username + default password you were given. On the FIRST
   login you must set your own password before the app opens.
3. If you had observations saved in this browser from before, a bar appears
   offering to import them into the shared database - click it once.
4. Log observations and generate reports. Everyone signed in sees the SAME
   shared data.

Branding & login experience: a premium glassmorphism login screen (Inter font,
white text) uses the robot logo, which also appears in the app header and as the
browser-tab favicon. After a successful login there is a short cinematic loading
animation (a silhouette forms from particles, then reassembles into the logo,
which pulses and fades to the app); it lasts ~3 seconds, respects the OS
"reduce motion" setting, and can be clicked to skip. To change the logo, replace
the base64 image data in index.html (the favicon <link> near the top, the header
<img>, the login overlay <img>, and the logoImg.src inside runIntro()).

Note: the app loads the shared data when you sign in. If your boss adds entries
while you're already looking at the page, refresh to see them.

---

## Editing the report prompt
The report generator now runs on Supabase. Open supabase/functions/generate-report/index.ts (the EDIT ZONE at the top has two
strings (SYSTEM_PROMPT, REPORT_INSTRUCTIONS) - reword them and redeploy. The
current version produces a detailed, analytical performance review: a summary,
the current evaluation date per robot, the Top 3 worst-performing bots (each as a
full paragraph explaining why it ranked, the recurring issues, their severity and
impact, the AI-inferred trend, and any sample link as evidence), a brief analysis
of the remaining bots, and prioritised recommendations. The AI infers each bot's
trend from the observations rather than from a fixed value.

## Changing the AI model / provider
- Model: set OPENAI_MODEL in Netlify, or change the default in the function.
- Provider: edit only callModel() in the function.

## Costs
- Supabase: free tier is plenty for a small team.
- Netlify: free tier is plenty here.
- OpenAI: a few thousandths of a dollar per report with gpt-5.4-mini. Set a
  spending limit in the OpenAI dashboard (Billing -> Limits) to be safe.

## Privacy
Generating a report sends the selected period's observations to OpenAI. Your
observation data is stored in your Supabase project. Confirm this is acceptable
for any confidential data before using it.

## Troubleshooting
- Login screen says "Not configured" - you didn't paste SUPABASE_URL /
  SUPABASE_ANON_KEY into index.html.
- Stuck on "set your new password" - that is expected on first login; choose a
  password (8+ chars) to continue. It won't ask again next time.
- "Invalid login credentials" - wrong username/password, or the user wasn't
  created in Supabase with <username>@LOGIN_EMAIL_DOMAIN and "Auto Confirm".
- "AI report unavailable" - the note shows why. Common causes: the OpenAI secret
  not set (supabase secrets set OPENAI_API_KEY=...), no OpenAI credit, or the
  Edge Function not deployed yet (Part C). Check: supabase functions logs
  generate-report. You still get the built-in report meanwhile.
- Reports say "session expired" - sign out and back in.
- Data doesn't appear for the other person - both must be signed in; refresh
  after the other person adds entries.
