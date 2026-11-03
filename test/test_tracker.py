"""Progress Tracker: board, filters, sorting, status, analytics, export."""
import sys, pathlib, csv, io as _io
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_trk.html")
D = {n: H.days_ago(n) for n in range(0, 20)}

tasks = [
    H.task("t1", D[4], "Alpha",   H.CRIS,  "completed", D[2] + "T10:00:00Z"),
    H.task("t2", D[4], "Charlie", H.CRIS,  "pending"),
    H.task("t3", D[3], "Alpha",   H.CRIS,  "in_progress"),
    H.task("t4", D[3], "Echo",    H.ADMIN, "completed", D[2] + "T11:00:00Z"),
    H.task("t5", D[2], "Echo",    H.ADMIN, "pending"),
    H.task("t6", D[2], "Fox",     None,    "pending"),
]
obs = [H.obs("o1", D[4], "Alpha", by=H.CRIS)]
asg = [H.assign("a1", H.CRIS, "Alpha", D[6]), H.assign("a2", H.ADMIN, "Echo", D[6])]

with sync_playwright() as pw:
    br = pw.chromium.launch()
    pg = br.new_page(viewport={"width": 1440, "height": 1300}, accept_downloads=True)
    H.watch_errors(pg, errs)
    dialogs = []; mode = {"accept": True}
    pg.on("dialog", lambda d: (dialogs.append(d.message),
                               d.accept() if mode["accept"] else d.dismiss()))
    pg.goto(url); H.seed(pg, observations=obs, assignments=asg, tasks=tasks); H.login(pg)

    chk("tab_exists", pg.is_visible("#tab-tracker"))
    pg.click("#tab-tracker"); pg.wait_for_timeout(1000)
    chk("page_opens", pg.is_visible("#page-tracker"))
    chk("other_pages_hidden", not pg.is_visible("#page-dashboard"))
    chk("rows_rendered", pg.eval_on_selector_all("#trk-body tr", "e => e.length") == 6)

    # ---- summary cards ----
    cards = pg.inner_text("#trk-cards")
    chk("cards_total", "TOTAL REVIEWS" in cards and "\n6" in "\n" + cards)
    chk("cards_completion_rate", "33%" in cards, "| 2 of 6 -> %s" % cards.replace("\n", " ")[-60:])

    # ---- the rule that matters: logs never complete a task ----
    chk("observation_does_not_complete",
        pg.evaluate("() => _tasks.find(t => t.id === 't2').status") == "pending")
    chk("but_logs_are_flagged", "has logs" in pg.inner_text("#trk-body"),
        "| t1/Alpha has an observation")

    # ---- filters ----
    pg.select_option("#trk-f-status", "pending"); pg.wait_for_timeout(500)
    chk("filter_status", pg.eval_on_selector_all("#trk-body tr", "e => e.length") == 3)
    chk("cards_follow_filter", "100%" not in pg.inner_text("#trk-cards"))
    pg.select_option("#trk-f-status", ""); pg.wait_for_timeout(300)

    pg.select_option("#trk-f-robot", "Alpha"); pg.wait_for_timeout(500)
    chk("filter_robot", pg.eval_on_selector_all("#trk-body tr", "e => e.length") == 2)
    pg.select_option("#trk-f-robot", ""); pg.wait_for_timeout(300)

    rid = pg.eval_on_selector("#trk-f-reviewer option:nth-child(3)", "e => e.value")
    pg.select_option("#trk-f-reviewer", rid); pg.wait_for_timeout(500)
    chk("filter_reviewer", pg.eval_on_selector_all("#trk-body tr", "e => e.length") in (2, 3))
    pg.select_option("#trk-f-reviewer", ""); pg.wait_for_timeout(300)

    pg.fill("#trk-from", D[3]); pg.wait_for_timeout(500)
    chk("filter_date_from", pg.eval_on_selector_all("#trk-body tr", "e => e.length") == 4)
    pg.fill("#trk-search", "fox"); pg.wait_for_timeout(500)
    chk("search_narrows", pg.eval_on_selector_all("#trk-body tr", "e => e.length") == 1)
    pg.click("#trk-clear"); pg.wait_for_timeout(500)
    chk("clear_restores", pg.eval_on_selector_all("#trk-body tr", "e => e.length") == 6)

    # ---- sorting ----
    # Read the underlying field for the row order: the Bot cell also renders a
    # "has logs" hint and the Status cell renders a <select> of every option,
    # so comparing cell TEXT would test the markup rather than the sort.
    def order(field):
        return pg.evaluate("""([f]) => [...document.querySelectorAll('#trk-body tr')]
            .map(tr => _tasks.find(t => t.id === tr.dataset.task))
            .map(t => f === 'status' ? ({pending:0, in_progress:1, completed:2})[t.status]
                                     : t[f])""", [field])

    chk("default_newest_first", order("obs_date") == sorted(order("obs_date"), reverse=True))
    pg.click('.trk-sort[data-sort="robot"]'); pg.wait_for_timeout(500)
    chk("sort_by_bot", order("robot") == sorted(order("robot")), "| %s" % order("robot"))
    pg.click('.trk-sort[data-sort="robot"]'); pg.wait_for_timeout(500)
    chk("sort_flips", order("robot") == sorted(order("robot"), reverse=True),
        "| %s" % order("robot"))
    chk("sort_arrow_shown", "\u2193" in pg.inner_text('.trk-sort[data-sort="robot"]'))
    pg.click('.trk-sort[data-sort="status"]'); pg.wait_for_timeout(500)
    chk("sort_by_status_is_workflow_order", order("status") == sorted(order("status")),
        "| pending -> in progress -> completed, not alphabetical: %s" % order("status"))

    # ---- changing status ----
    pg.click('.trk-sort[data-sort="date"]'); pg.wait_for_timeout(400)
    row = pg.locator('#trk-body tr[data-task="t2"]')
    row.locator(".trk-st").select_option("completed"); pg.wait_for_timeout(900)
    chk("status_saved", pg.evaluate("() => _tasks.find(t => t.id === 't2').status") == "completed")
    chk("completed_at_stamped",
        pg.evaluate("() => !!_tasks.find(t => t.id === 't2').completed_at"))
    chk("status_toast", pg.eval_on_selector_all(".fb-toast.fb-toast-on", "e => e.length") == 1)
    chk("tick_shown", "✓" in pg.locator('#trk-body tr[data-task="t2"]').inner_text())

    # reopening clears the completion stamp
    pg.locator('#trk-body tr[data-task="t2"] .trk-st').select_option("pending"); pg.wait_for_timeout(900)
    chk("reopen_clears_stamp",
        pg.evaluate("() => _tasks.find(t => t.id === 't2').completed_at") is None)

    # ---- mark done button ----
    pg.locator('#trk-body tr[data-task="t5"] .trk-done').click(); pg.wait_for_timeout(900)
    chk("mark_done_button", pg.evaluate("() => _tasks.find(t => t.id === 't5').status") == "completed")

    # ---- add, with duplicate guard ----
    pg.click("#trk-add-toggle"); pg.wait_for_timeout(400)
    pg.fill("#trk-n-date", D[1]); pg.select_option("#trk-n-robot", "Hugo")
    pg.select_option("#trk-n-reviewer", H.CRIS)
    pg.click("#trk-n-save"); pg.wait_for_timeout(900)
    chk("task_added", pg.evaluate("() => _tasks.length") == 7)
    pg.click("#trk-n-save"); pg.wait_for_timeout(700)
    chk("duplicate_refused", pg.evaluate("() => _tasks.length") == 7,
        "| %s" % pg.inner_text("#trk-n-status-msg"))
    chk("duplicate_explained", "already on the board" in pg.inner_text("#trk-n-status-msg"))

    # ---- create from assignments ----
    before = pg.evaluate("() => _tasks.length")
    pg.click("#trk-generate"); pg.wait_for_timeout(1200)
    after = pg.evaluate("() => _tasks.length")
    chk("generate_adds", after > before, "| %d -> %d" % (before, after))
    chk("generate_keeps_existing_status",
        pg.evaluate("() => _tasks.find(t => t.id === 't1').status") == "completed")
    gen_dups = pg.evaluate("""() => {
        const seen = new Set();
        return _tasks.filter(t => {
          const k = t.obs_date + '|' + t.robot + '|' + (t.reviewer_id || '');
          if (seen.has(k)) return true; seen.add(k); return false;
        }).length; }""")
    chk("generate_makes_no_duplicates", gen_dups == 0, "| %d dupes" % gen_dups)

    # ---- analytics ----
    chk("by_reviewer", pg.eval_on_selector_all("#trk-by-reviewer > div", "e => e.length") >= 2)
    chk("by_bot", pg.eval_on_selector_all("#trk-by-robot > div", "e => e.length") >= 3)
    chk("trend_drawn", pg.eval_on_selector_all("#trk-trend > div:first-child > div", "e => e.length") > 0)
    pg.select_option("#trk-trend-grain", "week"); pg.wait_for_timeout(600)
    chk("trend_by_week", pg.eval_on_selector_all("#trk-trend > div:first-child > div", "e => e.length") > 0)

    # ---- CSV ----
    with pg.expect_download() as dl:
        pg.click("#trk-export")
    path = dl.value.path()
    text = pathlib.Path(path).read_text(encoding="utf-8-sig")
    rows = list(csv.reader(_io.StringIO(text)))
    chk("csv_header", rows[0] == ["Date", "HBA reviewer", "Bot", "Status",
                                  "Completed", "Last updated", "Notes"], "| %s" % rows[0])
    chk("csv_row_count", len(rows) - 1 == pg.eval_on_selector_all("#trk-body tr", "e => e.length"),
        "| csv %d vs table %d" % (len(rows) - 1,
                                  pg.eval_on_selector_all("#trk-body tr", "e => e.length")))
    chk("csv_names_not_ids", not any("-" * 1 in r[1] and len(r[1]) > 30 for r in rows[1:]))
    chk("csv_filename", dl.value.suggested_filename.startswith("progress-tracker-"))

    pg.locator("#page-tracker").screenshot(path="/tmp/claude-0/tracker.png")

    # ---- permissions ----
    for who, role in (("cris", "editor"), ("ana", "viewer")):
        p2 = br.new_page(viewport={"width": 1440, "height": 1000})
        H.watch_errors(p2, errs)
        p2.goto(url); H.seed(p2, observations=obs, assignments=asg, tasks=tasks); H.login(p2, who)
        p2.click("#tab-tracker"); p2.wait_for_timeout(900)
        chk(role + "_sees_board", p2.eval_on_selector_all("#trk-body tr", "e => e.length") == 6)
        chk(role + "_cannot_add", not p2.is_visible("#trk-add-toggle"))
        chk(role + "_cannot_delete", p2.eval_on_selector_all("#trk-body .trk-del", "e => e.length") == 0)
        own = p2.eval_on_selector_all("#trk-body .trk-st", "e => e.length")
        chk(role + "_edits_only_own", own == (3 if role == "editor" else 0), "| %d editable" % own)
        p2.close()

    # ---- SQL not run ----
    p3 = br.new_page(viewport={"width": 1440, "height": 1000})
    H.watch_errors(p3, errs)
    p3.goto(url); H.seed(p3, observations=obs, tasks=[], missing=["review_tasks"]); H.login(p3)
    p3.click("#tab-tracker"); p3.wait_for_timeout(900)
    chk("missing_table_explained", "supabase-tracker.sql" in p3.inner_text("#trk-empty"))
    chk("missing_table_app_alive", p3.evaluate("() => entries.length") == 1)
    chk("missing_table_hides_actions", not p3.is_visible("#trk-add-toggle"))

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
