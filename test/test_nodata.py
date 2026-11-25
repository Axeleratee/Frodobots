"""No-data checks: form behaviour, excluded from performance counts, Logs badge + filter."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_nodata.html", config={"REST_DAYS": [], "REVIEW_DELAY_DAYS": 0})
D = {n: H.days_ago(n) for n in range(0, 40)}

obs = [
    H.obs("r1", D[1], "Alpha", by=H.CRIS, issues=("idle_hand",), severity=60),
    H.obs("r2", D[2], "Alpha", by=H.CRIS),
    H.obs("r3", D[3], "Echo",  by=H.CRIS),
]
# An inactive bot "checked" five times - four with the checkbox, one
# backfilled from a "no data" note.
for i, n in enumerate((1, 2, 3, 4)):
    obs.append(H.obs("nd%d" % i, D[n], "Fox", by=H.CRIS, no_data=True))
bf = H.obs("bf1", D[5], "Fox", by=H.CRIS)
bf["entry"].update({"noData": True, "issue": ["nodata"], "notes": "No data", "issue_before_backfill": ["none"]})
obs.append(bf)

def logs_for(pg, user):
    return pg.evaluate("""u => { const tr = document.querySelector('.perf-row[data-user="' + u + '"]');
                                 return tr ? +tr.children[2].textContent : null; }""", user)
def stat(pg, label):
    return pg.evaluate("""l => { const d = [...document.querySelectorAll('#perf-detail .fb-card > div:nth-of-type(2) > div')]
                                 .find(x => x.innerText.includes(l)); return d ? parseInt(d.innerText, 10) : null; }""", label)
def tile(pg, label):
    return pg.evaluate("""l => { const d = [...document.querySelectorAll('#perf-summary > div')].find(x => x.innerText.includes(l));
                                 return d ? parseInt(d.innerText, 10) : null; }""", label)
def rows(pg):
    return pg.eval_on_selector_all("#table-body tr[data-row]", "e => e.map(t => t.dataset.row)")

with sync_playwright() as pw:
    br = pw.chromium.launch()
    pg = br.new_context(viewport={"width": 1400, "height": 1100}, timezone_id="Asia/Manila").new_page()
    H.watch_errors(pg, errs); pg.on("dialog", lambda d: d.accept())
    pg.goto(url); H.seed(pg, observations=obs); H.login(pg)

    # ================= 1. form =================
    chk("label", "No data (bot inactive / nothing to review)" in pg.inner_text("#card-log"))
    pg.check("#f-nodata"); pg.wait_for_timeout(150)
    chk("task_disabled", pg.is_disabled("#f-task .ms-toggle"))
    chk("issue_disabled", pg.is_disabled("#f-issue .ms-toggle"))
    chk("severity_disabled", pg.is_disabled("#f-severity"))
    chk("notes_open", pg.is_enabled("#f-notes") and pg.locator("#f-notes").is_visible())
    chk("fields_still_visible", pg.locator("#f-task").is_visible())
    pg.uncheck("#f-nodata"); pg.wait_for_timeout(150)
    chk("re_enabled", pg.is_enabled("#f-task .ms-toggle") and pg.is_enabled("#f-severity"))

    # still needs bot and date
    pg.check("#f-nodata")
    pg.fill("#f-date", ""); pg.click("#btn-save"); pg.wait_for_timeout(300)
    chk("date_required", "required" in pg.inner_text("#save-status"), "| %s" % pg.inner_text("#save-status"))

    # save a no-data check with a reason
    pg.fill("#f-date", D[0]); pg.select_option("#f-robot", "Kilo")
    pg.fill("#f-notes", "bot offline all day")
    n0 = pg.evaluate("() => entries.length")
    pg.click("#btn-save"); pg.wait_for_timeout(700)
    e = pg.evaluate("() => entries[entries.length - 1]")
    chk("saved", pg.evaluate("() => entries.length") == n0 + 1)
    chk("saved_as_nodata", e["noData"] is True and e["issue"] == ["nodata"] and e["task"] == [] and e["severity"] == "",
        "| %s" % {k: e.get(k) for k in ("noData", "issue", "task", "severity")})
    chk("notes_kept", e["notes"] == "bot offline all day")
    chk("form_resets_enabled", (not pg.is_checked("#f-nodata")) and pg.is_enabled("#f-severity"))

    # editing a no-data check reopens it switched off, with its note
    pg.evaluate("id => startEdit(id)", e["id"]); pg.wait_for_timeout(300)
    chk("edit_checked", pg.is_checked("#f-nodata") and pg.is_disabled("#f-severity"))
    chk("edit_note", pg.input_value("#f-notes") == "bot offline all day")
    pg.click("#btn-cancel-edit"); pg.wait_for_timeout(200)

    # a normal observation still saves as before
    pg.fill("#f-date", D[0]); pg.select_option("#f-robot", "Hugo")
    pg.evaluate("() => taskMS.setValues(['sweep floor'])")
    pg.click("#btn-save"); pg.wait_for_timeout(700)
    e2 = pg.evaluate("() => entries[entries.length - 1]")
    chk("normal_save_unchanged", e2["robot"] == "Hugo" and not e2["noData"] and e2["issue"] == ["none"])

    # ================= 2. User Performance =================
    pg.click("#tab-performance"); pg.wait_for_timeout(900)
    pg.click('.perf-period .perf-win[data-win="30"]'); pg.wait_for_timeout(300)
    chk("table_logs_excludes_nodata", logs_for(pg, "cris") == 3, "| %s (was 8)" % logs_for(pg, "cris"))
    chk("summary_tile_nodata", tile(pg, "No-data checks") == 6, "| %s" % tile(pg, "No-data checks"))
    pg.click('.perf-row[data-user="cris"]'); pg.wait_for_timeout(400)
    chk("profile_obs", stat(pg, "Observations logged") == 3, "| %s" % stat(pg, "Observations logged"))
    chk("profile_nodata_card", stat(pg, "No-data checks") == 5, "| %s" % stat(pg, "No-data checks"))
    chk("profile_bots", stat(pg, "Bots covered") == 2, "| %s" % stat(pg, "Bots covered"))
    chips = pg.inner_text("#perf-detail").split("Bots covered\n")[-1].split("Recent activity")[0]
    chk("chips_no_inactive_bot", "Fox" not in chips and "Alpha" in chips, "| %s" % chips.replace("\n", " "))
    chk("issues_unchanged", stat(pg, "Issues found") == 1)
    total_bars = pg.evaluate("""() => [...document.querySelectorAll('#perf-detail svg rect title')]
        .reduce((n, t) => n + (parseInt(t.textContent.match(/(\\d+)\\s*(log|obs)/i)?.[1] || t.textContent.match(/:\\s*(\\d+)/)?.[1] || 0, 10)), 0)""")
    chk("activity_chart_excludes_nodata", total_bars == 3, "| %s" % total_bars)
    pg.click("#perf-back"); pg.wait_for_timeout(200)

    # ================= 3. AI report payload =================
    p = pg.evaluate("""() => {
        const inRange = entries.slice();
        return buildReportPayload({ start: null, end: null, inRange, byBot: {}, stats: {}, ranked: [] }).summary; }""")
    n_eval = sum(1 for o in obs if not o["entry"].get("noData")) + 1     # + the Hugo saved above
    chk("report_total_is_observations", p["totalObservations"] == n_eval, "| %s vs %s" % (p["totalObservations"], n_eval))
    chk("report_nodata_separate", p["noDataChecks"] == 6, "| %s" % p["noDataChecks"])

    # ================= 4. Logs tab =================
    pg.click("#tab-logs"); pg.wait_for_timeout(500)
    pg.click("#obs-head"); pg.wait_for_timeout(400)
    allr = rows(pg)
    chk("default_shows_all", len(allr) == len(obs) + 2 and pg.input_value("#filter-kind") == "", "| %d" % len(allr))
    badge = pg.evaluate("""() => { const c = r => document.querySelector('#table-body tr[data-row="' + r + '"] td').innerText;
                                   return [c('nd0'), c('bf1'), c('r1')]; }""")
    chk("badge_on_nodata", "No data" in badge[0] and "No data" in badge[1] and "No data" not in badge[2], "| %s" % badge)
    pg.select_option("#filter-kind", "obs"); pg.wait_for_timeout(250)
    r = rows(pg)
    chk("filter_observations_only", sorted(r) == sorted(["r1", "r2", "r3", e2["id"]]), "| %s" % r)
    pg.select_option("#filter-kind", "nodata"); pg.wait_for_timeout(250)
    r = rows(pg)
    chk("filter_nodata_only", len(r) == 6 and all(x.startswith(("nd", "bf")) or x == e["id"] for x in r), "| %s" % r)
    chk("header_says_filtered", " of " in pg.inner_text("#obs-head-count"))
    pg.click("#filter-clear"); pg.wait_for_timeout(250)
    chk("clear_resets_kind", pg.input_value("#filter-kind") == "" and len(rows(pg)) == len(allr))

    # ================= regressions =================
    st = pg.evaluate("""d => { const r = botDayRows(d, d).find(x => x.robot === 'Fox'); return r ? r.uploadStatus : 'none'; }""", D[2])
    chk("tracker_still_sees_check", st == "nodata", "| %s" % st)
    pg.click("#tab-dashboard"); pg.wait_for_timeout(300)
    fox = pg.evaluate("() => { const r = document.querySelector('#rank-list .rank-row[data-bot=\"Fox\"]'); return r ? +r.querySelector('.rank-val').textContent : null; }")
    chk("ranking_unchanged", fox == 0, "| %s" % fox)

    pg.click("#tab-logs"); pg.wait_for_timeout(300)
    pg.locator("#card-obs").screenshot(path="/tmp/nodata_logs.png")
    pg.click("#tab-dashboard"); pg.check("#f-nodata"); pg.wait_for_timeout(150)
    pg.locator("#card-log").screenshot(path="/tmp/nodata_form.png")

    chk("no_js_errors", not errs, "|%s" % errs[:3])
    br.close()

sys.exit(chk.report())
