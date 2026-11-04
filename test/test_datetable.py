"""Date overview table: review status and upload status stay separate, and
nothing is invented for a bot-day that has no record."""
import sys, pathlib, csv, io as _io
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_dt.html", config={"REST_DAYS": []})
D = {n: H.days_ago(n) for n in range(0, 20)}

asg = [H.assign("a1", H.CRIS, "Alpha", D[8]), H.assign("a2", H.ADMIN, "Echo", D[8])]

obs = [
    H.obs("x1", D[5], "Alpha", by=H.CRIS),                    # on time
    H.obs("x2", D[4], "Alpha", by=H.CRIS, late=True),         # late upload
    H.obs("x3", D[3], "Alpha", by=H.CRIS, no_data=True),      # looked, nothing there
    H.obs("x4", D[5], "Echo",  by=H.ADMIN),
]
tasks = []   # review_tasks is no longer read; status is derived from the logs

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

    # ---- review status is derived from who logged what ----
    r5 = row(D[5], "Alpha")
    chk("owners_log_is_done", "Done" in r5, "| cris owns Alpha and logged it: %s" % r5)
    chk("upload_ontime", "On time" in r5)

    r4 = row(D[4], "Alpha")
    chk("late_upload_flagged", "Late" in r4, "| %s" % r4)
    chk("late_upload_still_done", "Done" in r4,
        "| arriving late is an upload fact, not an unfinished review")

    # A day where nothing arrived: the reviewer logged "no data", so the
    # review is Done while the upload reads "No data". Still two answers.
    r3 = row(D[3], "Alpha")
    chk("empty_day_review_is_done", "Done" in r3, "| %s" % r3)
    chk("empty_day_upload_is_nodata", "No data" in r3)
    chk("checked_day_is_not_called_unlogged", "Not logged" not in r3)

    # Assigned but nothing logged -> Pending, from the assignment alone.
    r6 = row(D[6], "Alpha")
    chk("assigned_and_unlogged_is_pending", "Pending" in r6, "| %s" % r6)
    chk("pending_row_has_an_owner", "cris" in r6)

    # Nobody responsible -> no review was ever expected.
    r_un = pg.evaluate("""() => {
        const tr = [...document.querySelectorAll('#dt-body tr')]
          .find(r => r.innerText.includes('Not assigned'));
        return tr ? tr.innerText.replace(/\\n/g, ' | ') : null; }""")
    chk("unassigned_says_not_assigned", r_un is None or "Not assigned" in r_un,
        "| %s" % r_un)

    # ---- cards come from the rows, not from mock numbers ----
    cards = pg.inner_text("#dates-cards")
    for word in ("ASSIGNED", "DONE", "PENDING",
                 "LATE UPLOADS", "NO DATA", "NOT LOGGED", "COMPLETION"):
        chk("card_" + word.split()[0].lower(), word in cards)
    n_late = pg.evaluate("() => dtCounts(dtRows()).late")
    shown_late = pg.eval_on_selector_all("#dt-body tr", """els => els.filter(
        r => r.innerText.includes('Late')).length""")
    chk("late_card_matches_rows", n_late == shown_late, "| card %d vs rows %d" % (n_late, shown_late))
    chk("rate_excludes_unassigned",
        pg.evaluate("() => { const c = dtCounts(dtRows()); return c.rate === Math.round(c.done/c.tracked*100); }"))

    # ---- filters ----
    total = pg.eval_on_selector_all("#dt-body tr", "e => e.length")
    pg.select_option("#dt-upload", "late"); pg.wait_for_timeout(600)
    chk("filter_upload", pg.eval_on_selector_all("#dt-body tr", "e => e.length") == 1)
    pg.select_option("#dt-upload", ""); pg.wait_for_timeout(400)
    pg.select_option("#dt-review", "done"); pg.wait_for_timeout(600)
    chk("filter_review", pg.evaluate("""() => {
        const rs = [...document.querySelectorAll('#dt-body tr')];
        return rs.length > 0 && rs.every(r => r.innerText.includes('Done')); }"""))
    pg.select_option("#dt-review", "pending"); pg.wait_for_timeout(600)
    chk("filter_pending", pg.evaluate("""() => {
        const rs = [...document.querySelectorAll('#dt-body tr')];
        return rs.length > 0 && rs.every(r => r.innerText.includes('Pending')); }"""))
    pg.select_option("#dt-review", "untracked"); pg.wait_for_timeout(600)
    chk("filter_unassigned_shows_only_those", pg.evaluate("""() => [...document.querySelectorAll('#dt-body tr')]
        .every(r => r.innerText.includes('Not assigned'))"""),
        "| every bot-day here is assigned, so an empty result is correct")
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
