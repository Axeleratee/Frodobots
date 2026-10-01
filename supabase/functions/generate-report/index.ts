// ============================================================
//  QA REPORT GENERATOR - Supabase Edge Function (Deno)
// ============================================================
//  Moved here from Netlify so the OpenAI call is NOT bound by
//  Netlify's ~10s function timeout. Supabase Edge Functions allow
//  much longer execution, so long/detailed reports won't time out.
//
//  Deploy:
//    supabase functions deploy generate-report --no-verify-jwt
//  Set the OpenAI key as a secret (server-side, never in the browser):
//    supabase secrets set OPENAI_API_KEY=sk-...
//    (optional) supabase secrets set OPENAI_MODEL=gpt-5.4-mini
//
//  ┌──────────────────────────────────────────────────────────┐
//  │  EDIT ZONE - change how the report reads, anytime.        │
//  │  (Kept identical to the Netlify version.)                 │
//  └──────────────────────────────────────────────────────────┘

const SYSTEM_PROMPT = `
You are a senior QA analyst who writes concise, professional performance reviews
of teleoperated robots. You analyse the data rather than restating it: you assess
severity, infer trends, and explain your reasoning briefly. You are precise and
neutral, and you never invent data that is not present in the input.
`.trim();

const REPORT_INSTRUCTIONS = `
Using ONLY the observation data below, write a CONCISE, ANALYTICAL QA performance
review in clean Markdown. Analyse the data - do not merely restate it or dump raw
numbers. Keep it tight and precise: no padding, no repetition.

SEVERITY RATING (you compute this - do NOT list the raw per-observation numbers):
for each bot that has errors, take the AVERAGE of its numeric severity values
across its flagged observations and assign ONE rating:
  - Critical : average 80 or higher
  - High     : average 60-79
  - Moderate : average 40-59
  - Low      : average below 40
If a bot has flagged issues but no numeric severity values, judge the rating from
the issue types instead (repeated "major" issue types lean High/Critical; isolated
minor ones lean Low/Moderate). State the rating word (e.g. "Severity: High"); you
may cite the average once as brief support, but never list every individual number.

DATA COVERAGE vs QUALITY - keep these two apart:
An entry marked "no data" means the bot was NOT evaluated that day, so there is
nothing to judge about its behaviour. Exclude those entries from every quality
judgement (severity, trend, issue counts, the worst-bot ranking) - but they are
NOT invisible. They are a coverage finding, and coverage is reported in its own
section below. The same goes for entries with "lateUpload": true - the footage
arrived after the expected date, which is a process problem, not a behaviour one.
Use the pre-counted numbers in summary.coverage; do not recount the rows yourself.

TREND (you compute this): for each bot, compare its observations across their dates
and decide Improving, Declining, Unstable, or Steady. Ignore any
"computedTrendHint" value - derive the trend from the evidence. If there are too
few observations to judge, say "Insufficient data".

Write these sections, in this exact order:

## Summary
2-3 sentences: the reporting period, how many bots were evaluated, and the single
most important finding.

## Current evaluation date per robot
One bullet per robot: "**<robot>** - last evaluated <date>".

## Top 3 worst performing bots
The (up to) three worst-performing bots this period. For EACH one, write ONE SHORT
paragraph (about 2-3 sentences, NOT bullet points) that states its severity rating
and trend, the main recurring or significant issue(s) that drove the ranking, and
the likely impact on performance. If that bot's observations include a sample/video
link, add it at the end of the paragraph as evidence. Be precise, not wordy. If
fewer than three bots had errors, cover only those that did; if none did, say so.

## Remaining bots
For every OTHER bot, ONE sentence each: overall performance, its severity rating
(or "no issues observed"), and its trend. If a bot only has "no data" entries, note
it was not evaluated this period.

## Data coverage
Report what could NOT be evaluated this period, using summary.coverage:
- One opening line with the overall split: how many entries were evaluated, how
  many were "no data", and how many arrived as late uploads.
- Then one bullet for each bot that has any noData, lateUploads, or
  datesWithNoEntryAtAll above zero, in the form:
  "**<robot>** - <n> no data, <n> late upload(s), <n> date(s) with no entry at all".
  Skip bots where all three are zero. If every bot is clean, say so in one line.
- Close with one sentence on what the gaps mean for confidence in this report -
  for example, that a bot with few evaluated sessions cannot be ranked reliably.
Treat missing data as a teleoperation/upload issue, never as a fault of the
reviewer who logged it.

## Recommendations
3-5 short bullet points: concrete, prioritised focus areas for the annotation and
teleoperation teams, grounded in the analysis above. If coverage gaps are the
biggest problem this period, say so and make that the first bullet.

Rules:
- Base every statement strictly on the data. Never invent robots, dates, issues,
  numbers, links, or trends that are not present.
- Analyse, do not repeat. Do not list raw per-observation severity numbers.
- Include a sample link only if it actually appears in that bot's data.
- No preamble like "Here is the report". Keep the whole report concise.
`.trim();

//  ┌──────────────────────────────────────────────────────────┐
//  │  LOGIC - you normally don't need to change anything below.│
//  └──────────────────────────────────────────────────────────┘

const PROGRESSION_INSTRUCTIONS = `
Using ONLY the observation data below, write a CONCISE, ANALYTICAL PROGRESSION
REVIEW for ONE robot over the given period, in clean Markdown. Analyse how the
bot changed over time - do not merely list the observations back.

SEVERITY RATING (you compute this - do NOT list raw per-observation numbers):
take the AVERAGE of the numeric severity values across this bot's flagged
observations and assign ONE rating:
  - Critical : average 80 or higher
  - High     : average 60-79
  - Moderate : average 40-59
  - Low      : average below 40
If there are flagged issues but no numeric severity values, judge from the issue
types instead. If there are no errors at all, say "Severity: no issues observed".

TREND: you infer it yourself by comparing earlier dates against later dates -
Improving, Declining, Unstable, or Steady. Justify it in a few words. If only one
evaluated session exists, say a trend cannot be established yet.

Entries marked "no data" mean the bot was NOT evaluated that day, so there is
nothing to judge about its behaviour. Exclude them from every quality judgement
(severity, trend, recurring issues) - but they are NOT invisible: report them in
the Data coverage section below. Entries with "lateUpload": true mean the footage
arrived after the expected date; that is a process problem, not a behaviour one,
and belongs in the same section. Use the pre-counted numbers in summary.coverage
rather than recounting rows yourself.

STRUCTURE (use these exact headings):

## Overview
One short paragraph: which bot, the period, how many sessions were evaluated, and
the single most important takeaway. State **Severity: <rating>** and
**Trend: <trend>** here in bold.

## Day-by-day progression
One SHORT line per date, in chronological order, in the form:
- **<date>** - what was observed and whether it improved or worsened versus the
  previous date.
For a date whose entries are all "no data", still give it a line, written as
"- **<date>** - not evaluated (no data)." so the gap is visible in the timeline
instead of silently disappearing. Mark a late upload on its line too.
Keep each line to one sentence. Do not repeat the same wording every line.

## Recurring issues
A few bullets naming the issues that appear more than once, with how many times
each occurred and what they suggest about the underlying cause. If nothing
recurs, say so in one line.

## Data coverage
Two or three sentences using summary.coverage: how many entries were evaluated,
how many were "no data", how many arrived late, and how many dates in the period
have no entry at all for this bot. Say plainly what that does to confidence in
the trend above - a trend drawn from two evaluated sessions is weak, and you
should say so. Treat missing data as a teleoperation/upload issue, never as a
fault of the reviewer who logged it. If coverage is complete, say so in one line.

## Conclusion and recommendations
2-4 bullets with concrete, actionable next steps for this specific bot. If the
main problem is missing or late data rather than behaviour, say that first.

RULES:
- Never invent data. If something is not in the input, do not mention it.
- Refer to the bot by name.
- Keep the whole report tight - no filler, no restating these instructions.
`.trim();

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  let body: any;
  try { body = await req.json(); }
  catch { return json({ error: "invalid_json" }, 400); }

  // Verify the caller is a logged-in user. SUPABASE_URL and
  // SUPABASE_ANON_KEY are injected automatically into Edge Functions.
  const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
  const SUPABASE_ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY");
  const token = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  if (SUPABASE_URL && SUPABASE_ANON_KEY) {
    if (!token) return json({ error: "unauthorized" }, 401);
    let userId = "";
    try {
      const u = await fetch(SUPABASE_URL + "/auth/v1/user", {
        headers: { apikey: SUPABASE_ANON_KEY, Authorization: "Bearer " + token },
      });
      if (!u.ok) return json({ error: "unauthorized" }, 401);
      const uj = await u.json();
      userId = uj?.id || "";
    } catch (e) {
      return json({ error: "auth_check_failed", detail: String((e as Error)?.message || e) }, 502);
    }
    // Only Admin and Viewer may generate AI reports (Editors are blocked to avoid waste).
    try {
      const pr = await fetch(
        SUPABASE_URL + "/rest/v1/profiles?id=eq." + userId + "&select=role",
        { headers: { apikey: SUPABASE_ANON_KEY, Authorization: "Bearer " + token } },
      );
      const rows = pr.ok ? await pr.json() : [];
      const role = Array.isArray(rows) && rows[0] ? rows[0].role : "viewer";
      if (role !== "admin" && role !== "viewer") {
        return json({ error: "forbidden", detail: "Your role is not allowed to generate reports." }, 403);
      }
    } catch (e) {
      return json({ error: "role_check_failed", detail: String((e as Error)?.message || e) }, 502);
    }
  }

  const apiKey = Deno.env.get("OPENAI_API_KEY");
  if (!apiKey) return json({ error: "server_missing_openai_api_key" }, 500);
  const model = Deno.env.get("OPENAI_MODEL") || "gpt-5.4-mini";

  // "progression" = single-bot day-by-day review; anything else = weekly summary.
  const instructions =
    body.mode === "progression" ? PROGRESSION_INSTRUCTIONS : REPORT_INSTRUCTIONS;

  const userContent =
    instructions + "\n\nOBSERVATION DATA (JSON):\n" + JSON.stringify(body.report || {}, null, 2);

  try {
    const text = await callModel(apiKey, model, SYSTEM_PROMPT, userContent);
    if (!text) return json({ error: "empty_response" }, 502);
    return json({ report: text, model });
  } catch (e) {
    return json({ error: "model_request_failed", detail: String((e as Error)?.message || e) }, 502);
  }
});

// The one place that knows about a specific provider.
async function callModel(apiKey: string, model: string, system: string, user: string): Promise<string> {
  const r = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + apiKey },
    body: JSON.stringify({
      model,
      messages: [
        { role: "system", content: system },
        { role: "user", content: user },
      ],
    }),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data?.error?.message || ("OpenAI HTTP " + r.status));
  return String(data?.choices?.[0]?.message?.content || "").trim();
}

function json(obj: unknown, status = 200): Response {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...cors, "Content-Type": "application/json" },
  });
}
