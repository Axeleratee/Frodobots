"""Manual mode: the reviewer marks a review done themselves.

Pinned to AUTO_COMPLETE_ON_LOG=false; test_autocomplete covers the default."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_done.html", config={"AUTO_COMPLETE_ON_LOG": False})
D = {n: H.days_ago(n) for n in range(0, 12)}
asg = [H.assign("a1", H.ADMIN, "Alpha", D[9]), H.assign("a2", H.ADMIN, "Echo", D[9])]

def fresh(br, tasks=None, obs=None, who="boss"):
    pg = br.new_page(viewport={"width": 1440, "height": 1100})
    H.watch_errors(pg, errs)
    pg.on("dialog", lambda d: d.accept())
    pg.goto(url); H.seed(pg, observations=obs or [], assignments=asg, tasks=tasks or [])
    H.login(pg, who)
    return pg

def status_of(pg, date, bot):
    return pg.evaluate("""([d,b]) => {
        const t = _tasks.find(x => x.obs_date === d && x.robot === b);
        return t ? t.status : null; }""", [date, bot])

with sync_playwright() as pw:
    br = pw.chromium.launch()

    # ---- the checkbox exists where the logging happens ----
    pg = fresh(br)
    chk("checkbox_in_log_form", pg.is_visible("#f-done"))
    chk("checkbox_off_by_default", pg.eval_on_selector("#f-done", "e => !e.checked"))

    # ---- logging WITHOUT ticking it must not complete anything ----
    pg.fill("#f-date", D[5]); pg.select_option("#f-robot", "Alpha"); pg.wait_for_timeout(300)
    pg.click("#f-task"); pg.wait_for_timeout(200)
    pg.click("#f-task .ms-opt:has-text('sweep floor')")
    pg.click("#card-log >> text=Log an observation"); pg.wait_for_timeout(250)
    pg.click("#btn-save"); pg.wait_for_timeout(1100)
    chk("plain_log_does_not_complete", status_of(pg, D[5], "Alpha") is None,
        "| the original rule still holds")
    chk("observation_saved", pg.evaluate("() => entries.length") == 1)

    # ---- ticking it finishes that bot-day, creating the task if needed ----
    pg.fill("#f-date", D[4]); pg.select_option("#f-robot", "Alpha"); pg.wait_for_timeout(300)
    pg.click("#f-task"); pg.wait_for_timeout(200)
    pg.click("#f-task .ms-opt:has-text('sweep floor')")
    pg.click("#card-log >> text=Log an observation"); pg.wait_for_timeout(250)
    pg.check("#f-done")
    pg.click("#btn-save"); pg.wait_for_timeout(1300)
    chk("tick_completes", status_of(pg, D[4], "Alpha") == "completed",
        "| %s" % status_of(pg, D[4], "Alpha"))
    chk("toast_says_so", "marked done" in pg.inner_text(".fb-toast"),
        "| %s" % pg.inner_text(".fb-toast"))
    chk("checkbox_resets", pg.eval_on_selector("#f-done", "e => !e.checked"))

    # ---- "no data" is definitive, so it closes on its own ----
    pg.fill("#f-date", D[3]); pg.select_option("#f-robot", "Echo"); pg.wait_for_timeout(300)
    pg.check("#f-nodata"); pg.wait_for_timeout(200)
    chk("done_not_ticked", pg.eval_on_selector("#f-done", "e => !e.checked"))
    pg.click("#btn-save"); pg.wait_for_timeout(1300)
    chk("nodata_completes_itself", status_of(pg, D[3], "Echo") == "completed",
        "| nothing to come back to: %s" % status_of(pg, D[3], "Echo"))

    # ---- an existing task is advanced, not duplicated ----
    pg2 = fresh(br, tasks=[H.task("t1", D[6], "Alpha", H.ADMIN, "in_progress")])
    pg2.fill("#f-date", D[6]); pg2.select_option("#f-robot", "Alpha"); pg2.wait_for_timeout(300)
    pg2.click("#f-task"); pg2.wait_for_timeout(200)
    pg2.click("#f-task .ms-opt:has-text('sweep floor')")
    pg2.click("#card-log >> text=Log an observation"); pg2.wait_for_timeout(250)
    pg2.check("#f-done")
    pg2.click("#btn-save"); pg2.wait_for_timeout(1300)
    chk("existing_task_advanced", status_of(pg2, D[6], "Alpha") == "completed")
    chk("no_duplicate_task", pg2.evaluate("() => _tasks.length") == 1,
        "| %d tasks" % pg2.evaluate("() => _tasks.length"))
    pg2.close()

    # ---- bulk, for catching up ----
    tasks = [H.task("b%d" % n, D[n], "Alpha", H.ADMIN, "pending") for n in range(2, 8)]
    tasks.append(H.task("done1", D[8], "Alpha", H.ADMIN, "completed", D[8] + "T09:00:00Z"))
    pg3 = fresh(br, tasks=tasks)
    pg3.click("#tab-tracker"); pg3.wait_for_timeout(1000)
    chk("bulk_offered", pg3.is_visible("#trk-bulk"))
    chk("bulk_counts_only_unfinished", "6" in pg3.inner_text("#trk-bulk"),
        "| %s" % pg3.inner_text("#trk-bulk"))

    # it must respect the filters
    pg3.select_option("#trk-f-status", "pending"); pg3.wait_for_timeout(500)
    pg3.fill("#trk-from", D[4]); pg3.wait_for_timeout(600)
    shown = pg3.eval_on_selector_all("#trk-body tr", "e => e.length")
    pg3.click("#trk-bulk"); pg3.wait_for_timeout(1600)
    done = pg3.evaluate("() => _tasks.filter(t => t.status === 'completed').length")
    chk("bulk_respects_filters", done == shown + 1,
        "| %d shown + 1 already done -> %d completed" % (shown, done))
    chk("bulk_left_the_rest", pg3.evaluate("() => _tasks.filter(t => t.status === 'pending').length") > 0)
    pg3.close()

    # ---- an editor may only bulk-finish their own ----
    mixed = [H.task("m1", D[3], "Alpha", H.CRIS, "pending"),
             H.task("m2", D[3], "Echo", H.ADMIN, "pending")]
    pg4 = fresh(br, tasks=mixed, who="cris")
    pg4.click("#tab-tracker"); pg4.wait_for_timeout(1000)
    chk("editor_bulk_counts_own_only", "1" in pg4.inner_text("#trk-bulk"),
        "| %s" % pg4.inner_text("#trk-bulk"))
    pg4.click("#trk-bulk"); pg4.wait_for_timeout(1500)
    chk("editor_finished_own",
        pg4.evaluate("() => _tasks.find(t => t.id === 'm1').status") == "completed")
    chk("editor_left_others",
        pg4.evaluate("() => _tasks.find(t => t.id === 'm2').status") == "pending")
    pg4.close()

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
