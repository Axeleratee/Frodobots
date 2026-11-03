"""Date overview table: review status and upload status stay separate, and
nothing is invented for a bot-day that has no record."""
import sys, pathlib, csv, io as _io
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_dt.html")
D = {n: H.days_ago(n) for n in range(0, 20)}

asg = [H.assign("a1", H.CRIS, "Alpha", D[8]), H.assign("a2", H.ADMIN, "Echo", D[8])]

obs = [
    H.obs("x1", D[5], "Alpha", by=H.CRIS),                    # on time
    H.obs("x2", D[4], "Alpha", by=H.CRIS, late=True),         # late upload
    H.obs("x3", D[3], "Alpha", by=H.CRIS, no_data=True),      # looked, nothing there
    H.obs("x4", D[5], "Echo",  by=H.ADMIN),
]
tasks = [
    # finished the review of a day where NOTHING arrived - the two statuses
    # must not contaminate each other
    H.task("k1", D[3], "Alpha", H.CRIS, "completed", D[2] + "T09:00:00Z"),
    H.task("k2", D[4], "Alpha", H.CRIS, "in_progress"),
    H.task("k3", D[5], "Alpha", H.CRIS, "pending"),
]

with sync_playwright() as pw:
    br = pw.chromium.launch()
    pg = br.new_page(viewport={"width": 1440, "height": 1300}, accept_downloads=True)
    H.watch_errors(pg, errs)
    pg.goto(url); H.seed(pg, observations=obs, assignments=asg, tasks=tasks); H.login(pg)
    pg.click("#tab-logs"); pg.wait_for_timeout(1100)

    chk("table_is_default", pg.is_visible("#dates-table-wrap"))
    # The calendar's own summary line and hint must not linger over the table.
    chk("old_summary_hidden", not pg.is_visible("#dates-summary"))
    chk("hint_matches_view", "One row per bot per day" in pg.inner_text("#dates-hint"),
        "| %s" % pg.inner_text("#dates-hint")[:60])
    chk("rows_exist", pg.eval_on_selector_all("#dt-body tr", "e => e.length") > 0)

    def row(date, bot):
        return pg.evaluate("""([d,b]) => {
            const tr = [...document.querySelectorAll('#dt-body tr')]
              .find(r => r.dataset.date === d && r.dataset.bot === b);
            return tr ? tr.innerText.replace(/\\n/g, ' | ') : null; }""", [date, bot])

    # ---- the rule: a logged observation never completes a review ----
    r5 = row(D[5], "Alpha")
    chk("logs_do_not_complete", "Pending" in r5, "| %s" % r5)
    chk("upload_ontime", "On time" in r5)

    r4 = row(D[4], "Alpha")
    chk("late_upload_flagged", "Late" in r4, "| %s" % r4)
    chk("review_independent_of_upload", "In progress" in r4)

    # ---- the case that proves they are separate ----
    r3 = row(D[3], "Alpha")
    # The reviewer looked, nothing had arrived, and they finished the review.
    # Upload says "No data" (checked, none arrived), NOT "Not logged".
    chk("completed_review_of_empty_day", "Completed" in r3 and "No data" in r3,
        "| %s" % r3)
    chk("checked_day_is_not_called_unlogged", "Not logged" not in r3)

    # ---- no record invented ----
    r6 = row(D[6], "Alpha")
    chk("no_task_says_not_tracked", "Not tracked" in r6, "| %s" % r6)
    chk("no_task_is_not_pending", "Pending" not in r6)

    # ---- cards come from the rows, not from mock numbers ----
    cards = pg.inner_text("#dates-cards")
    for word in ("ASSIGNED", "COMPLETED", "IN PROGRESS", "PENDING",
                 "LATE UPLOADS", "NO DATA", "NOT LOGGED", "COMPLETION"):
        chk("card_" + word.split()[0].lower(), word in cards)
    n_late = pg.evaluate("() => dtCounts(dtRows()).late")
    shown_late = pg.eval_on_selector_all("#dt-body tr", """els => els.filter(
        r => r.innerText.includes('Late')).length""")
    chk("late_card_matches_rows", n_late == shown_late, "| card %d vs rows %d" % (n_late, shown_late))
    chk("rate_excludes_untracked",
        pg.evaluate("() => { const c = dtCounts(dtRows()); return c.rate === Math.round(c.completed/c.tracked*100); }"))

    # ---- filters ----
    total = pg.eval_on_selector_all("#dt-body tr", "e => e.length")
    pg.select_option("#dt-upload", "late"); pg.wait_for_timeout(600)
    chk("filter_upload", pg.eval_on_selector_all("#dt-body tr", "e => e.length") == 1)
    pg.select_option("#dt-upload", ""); pg.wait_for_timeout(400)
    pg.select_option("#dt-review", "completed"); pg.wait_for_timeout(600)
    chk("filter_review", pg.eval_on_selector_all("#dt-body tr", "e => e.length") == 1)
    pg.select_option("#dt-review", "untracked"); pg.wait_for_timeout(600)
    chk("filter_untracked", pg.eval_on_selector_all("#dt-body tr", "e => e.length") >= 1)
    pg.select_option("#dt-review", ""); pg.wait_for_timeout(400)
    pg.select_option("#dt-robot", "Echo"); pg.wait_for_timeout(600)
    chk("filter_bot", pg.evaluate("""() => [...document.querySelectorAll('#dt-body tr')]
        .every(r => r.dataset.bot === 'Echo')"""))
    pg.select_option("#dt-robot", ""); pg.wait_for_timeout(400)
    pg.fill("#dt-search", "alpha"); pg.wait_for_timeout(600)
    chk("search", pg.evaluate("""() => [...document.querySelectorAll('#dt-body tr')]
        .every(r => r.dataset.bot === 'Alpha')"""))
    pg.click("#dt-clear"); pg.wait_for_timeout(600)
    chk("clear_restores", pg.eval_on_selector_all("#dt-body tr", "e => e.length") == total)

    # ---- sorting ----
    def order(f):
        return pg.evaluate("""([f]) => [...document.querySelectorAll('#dt-body tr')]
            .map(r => f === 'date' ? r.dataset.date : r.dataset.bot)""", [f])
    chk("default_newest_first", order("date") == sorted(order("date"), reverse=True))
    pg.click('.dt-sort[data-sort="robot"]'); pg.wait_for_timeout(600)
    chk("sort_by_bot", order("bot") == sorted(order("bot")))
    pg.click('.dt-sort[data-sort="robot"]'); pg.wait_for_timeout(600)
    chk("sort_flips", order("bot") == sorted(order("bot"), reverse=True))
    pg.click('.dt-sort[data-sort="date"]'); pg.wait_for_timeout(600)

    # ---- row click opens the logs for that bot-day ----
    first = pg.locator("#dt-body tr").first
    d0, b0 = first.get_attribute("data-date"), first.get_attribute("data-bot")
    first.click(); pg.wait_for_timeout(900)
    chk("row_click_filters_logs",
        pg.input_value("#filter-from") == d0 and pg.input_value("#filter-robot") == b0,
        "| %s %s" % (b0, d0))

    # ---- the other views still work ----
    pg.click("#tab-logs"); pg.wait_for_timeout(600)
    pg.click("#dates-view-map"); pg.wait_for_timeout(900)
    chk("calendar_preserved", pg.eval_on_selector_all("#dates-heatmap .hm-cell", "e => e.length") > 0)
    chk("cards_hidden_off_table", not pg.is_visible("#dates-cards"))
    pg.click("#dates-view-bot"); pg.wait_for_timeout(1100)
    chk("by_bot_preserved", pg.eval_on_selector_all("#dates-matrix .hm-cell", "e => e.length") > 0)
    pg.click("#dates-view-list"); pg.wait_for_timeout(800)
    chk("list_preserved", pg.eval_on_selector_all("#dates-list .date-row", "e => e.length") > 0)
    pg.click("#dates-view-table"); pg.wait_for_timeout(800)
    chk("back_to_table", pg.eval_on_selector_all("#dt-body tr", "e => e.length") == total)

    # ---- breakdown ----
    chk("by_reviewer", pg.eval_on_selector_all("#dt-by-reviewer > div", "e => e.length") >= 1)
    chk("by_bot_blocks", pg.eval_on_selector_all("#dt-by-robot > div", "e => e.length") >= 2)

    # ---- CSV ----
    with pg.expect_download() as dl:
        pg.click("#dt-export")
    rows = list(csv.reader(_io.StringIO(
        pathlib.Path(dl.value.path()).read_text(encoding="utf-8-sig"))))
    chk("csv_header", rows[0] == ["Date", "HBA reviewer", "Bot", "Review status",
                                  "Upload status", "Observations", "Last updated"], "| %s" % rows[0])
    chk("csv_matches_table", len(rows) - 1 == total, "| %d vs %d" % (len(rows) - 1, total))

    pg.locator("#card-dates").screenshot(path="/tmp/claude-0/datetable.png")

    # ---- nothing set up yet: say what is needed, invent nothing ----
    p2 = br.new_page(viewport={"width": 1440, "height": 900})
    H.watch_errors(p2, errs)
    p2.goto(url); H.seed(p2, observations=[], assignments=[], tasks=[]); H.login(p2)
    p2.click("#tab-logs"); p2.wait_for_timeout(900)
    chk("empty_says_what_to_add", "Assignments" in p2.inner_text("#dt-empty"))
    chk("empty_has_no_fake_rows", p2.eval_on_selector_all("#dt-body tr", "e => e.length") == 0)

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
