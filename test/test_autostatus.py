"""Status is derived from the logs. Nothing is ticked, nothing is stored."""
import sys, pathlib, csv, io as _io
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_auto.html", config={"REST_DAYS": []})
D = {n: H.days_ago(n) for n in range(0, 14)}

# cris owns Alpha and Charlie; boss owns Echo. All from D[8].
asg = [H.assign("a1", H.CRIS, "Alpha", D[8]),
       H.assign("a2", H.CRIS, "Charlie", D[8]),
       H.assign("a3", H.ADMIN, "Echo", D[8])]

obs = [
    H.obs("o1", D[5], "Alpha", by=H.CRIS),                 # cris did his own
    H.obs("o2", D[5], "Alpha", by=H.CRIS, late=True),      # twice -> still ONE review
    H.obs("o3", D[4], "Charlie", by=H.ADMIN),              # boss logged cris's bot
    H.obs("o4", D[3], "Echo", by=H.ADMIN, no_data=True),   # "no data" is still a log
]

def st(pg, date, bot, who):
    return pg.evaluate("""([d,b,u]) => {
        const r = allExpected().find(x => x.obs_date === d && x.robot === b && x.reviewer_id === u);
        return r ? r.status : null; }""", [date, bot, who])

with sync_playwright() as pw:
    br = pw.chromium.launch()
    pg = br.new_page(viewport={"width": 1440, "height": 1200}, accept_downloads=True)
    H.watch_errors(pg, errs); pg.on("dialog", lambda d: d.accept())
    pg.goto(url); H.seed(pg, observations=obs, assignments=asg); H.login(pg)

    # ---- the rules ----
    chk("logged_is_done", st(pg, D[5], "Alpha", H.CRIS) == "done")
    chk("unlogged_is_pending", st(pg, D[6], "Alpha", H.CRIS) == "pending")
    chk("nodata_counts_as_logged", st(pg, D[3], "Echo", H.ADMIN) == "done",
        "| the reviewer looked and reported nothing arrived")
    chk("two_logs_are_one_review",
        pg.evaluate("""([d]) => allExpected()
            .filter(r => r.obs_date === d && r.robot === 'Alpha').length""", [D[5]]) == 1)
    chk("someone_elses_log_does_not_close_it", st(pg, D[4], "Charlie", H.CRIS) == "pending",
        "| boss logged it, but it is cris's assignment")
    chk("other_bots_untouched", st(pg, D[5], "Charlie", H.CRIS) == "pending",
        "| one observation must not mark every bot done")
    chk("pending_comes_from_assignments",
        pg.evaluate("() => allExpected().length") > len(obs),
        "| days with no logs at all still appear")

    # ---- nothing to click ----
    pg.click("#tab-tracker"); pg.wait_for_timeout(1100)
    chk("no_status_dropdown", pg.eval_on_selector_all("#trk-body select", "e => e.length") == 0)
    chk("no_mark_done", pg.eval_on_selector_all("#trk-body button", "e => e.length") == 0)
    for gone in ("trk-add-toggle", "trk-generate", "trk-bulk", "trk-catchup", "f-done"):
        chk("removed_" + gone, pg.eval_on_selector_all("#" + gone, "e => e.length") == 0)
    chk("four_columns", pg.eval_on_selector_all("#trk-body tr:first-child td", "e => e.length") == 4)

    # ---- live sync: save ----
    before = pg.evaluate("([d]) => allExpected().filter(r => r.obs_date === d && r.robot === 'Charlie' && r.status === 'done').length", [D[6]])
    pg.click("#tab-dashboard"); pg.wait_for_timeout(600)
    pg.fill("#f-date", D[6]); pg.select_option("#f-robot", "Charlie"); pg.wait_for_timeout(300)
    pg.click("#f-task"); pg.wait_for_timeout(200)
    pg.click("#f-task .ms-opt:has-text('sweep floor')")
    pg.click("#card-log >> text=Log an observation"); pg.wait_for_timeout(250)
    pg.click("#btn-save"); pg.wait_for_timeout(1300)
    chk("save_flips_to_done", st(pg, D[6], "Charlie", H.ADMIN) is None
        and st(pg, D[6], "Charlie", H.CRIS) == "pending", "| saved as boss, not cris's")
    # log it as the owner this time
    pg.evaluate("""([d]) => {
        const e = entries.find(x => x.date === d && x.robot === 'Charlie');
        e._by = 'uid-cris@robotqa.local'; refreshTeamViews(); }""", [D[6]])
    pg.wait_for_timeout(500)
    chk("owners_log_flips_to_done", st(pg, D[6], "Charlie", H.CRIS) == "done")

    # ---- live sync: no refresh needed ----
    pg.click("#tab-tracker"); pg.wait_for_timeout(900)
    done_now = pg.evaluate("() => trkCounts(trkFiltered()).done")
    pg.click("#tab-dashboard"); pg.wait_for_timeout(500)
    pg.fill("#f-date", D[7]); pg.select_option("#f-robot", "Echo"); pg.wait_for_timeout(300)
    pg.click("#f-task"); pg.wait_for_timeout(200)
    pg.click("#f-task .ms-opt:has-text('sweep floor')")
    pg.click("#card-log >> text=Log an observation"); pg.wait_for_timeout(250)
    pg.click("#btn-save"); pg.wait_for_timeout(1300)
    pg.click("#tab-tracker"); pg.wait_for_timeout(700)
    chk("tracker_updates_without_reload",
        pg.evaluate("() => trkCounts(trkFiltered()).done") == done_now + 1,
        "| %d -> %d" % (done_now, pg.evaluate("() => trkCounts(trkFiltered()).done")))

    # ---- live sync: delete reverts to Pending ----
    pg.click("#tab-logs"); pg.wait_for_timeout(700)
    pg.evaluate("""([d]) => {
        const e = entries.find(x => x.date === d && x.robot === 'Echo');
        return dbDelete(e.id).then(() => {
          entries = entries.filter(x => x.id !== e.id);
          render(); renderRecent(); refreshTeamViews(); }); }""", [D[7]])
    pg.wait_for_timeout(900)
    chk("delete_reverts_to_pending", st(pg, D[7], "Echo", H.ADMIN) == "pending",
        "| %s" % st(pg, D[7], "Echo", H.ADMIN))

    # ---- analytics ----
    pg.click("#tab-tracker"); pg.wait_for_timeout(900)
    cards = pg.inner_text("#trk-cards")
    for w in ("ASSIGNED REVIEWS", "DONE", "PENDING", "COMPLETION RATE"):
        chk("card_" + w.split()[0].lower(), w in cards)
    c = pg.evaluate("() => trkCounts(trkFiltered())")
    chk("counts_add_up", c["done"] + c["pending"] == c["total"],
        "| %d + %d = %d" % (c["done"], c["pending"], c["total"]))
    chk("rate_matches", c["rate"] == round(c["done"] / c["total"] * 100))
    chk("per_reviewer", pg.eval_on_selector_all("#trk-by-reviewer > div", "e => e.length") >= 2)
    chk("per_bot", pg.eval_on_selector_all("#trk-by-robot > div", "e => e.length") >= 3)

    # ---- filters, sorting, CSV still work ----
    pg.select_option("#trk-f-status", "pending"); pg.wait_for_timeout(600)
    chk("filter_pending", pg.evaluate("""() => [...document.querySelectorAll('#trk-body tr')]
        .every(r => r.innerText.includes('Pending'))"""))
    pg.select_option("#trk-f-status", "done"); pg.wait_for_timeout(600)
    chk("filter_done", pg.evaluate("""() => [...document.querySelectorAll('#trk-body tr')]
        .every(r => r.innerText.includes('Done'))"""))
    pg.select_option("#trk-f-status", ""); pg.wait_for_timeout(500)
    pg.click('.trk-sort[data-sort="robot"]'); pg.wait_for_timeout(600)
    bots = pg.eval_on_selector_all("#trk-body tr", "e => e.map(r => r.dataset.bot)")
    chk("sort_by_bot", bots == sorted(bots))

    with pg.expect_download() as dl:
        pg.click("#trk-export")
    rows = list(csv.reader(_io.StringIO(
        pathlib.Path(dl.value.path()).read_text(encoding="utf-8-sig"))))
    chk("csv_four_columns", rows[0] == ["Date", "HBA reviewer", "Bot", "Status"], "| %s" % rows[0])
    chk("csv_values", all(r[3] in ("Done", "Pending") for r in rows[1:]))

    pg.locator("#page-tracker").screenshot(path="/tmp/claude-0/autostatus.png")

    # clicking a row opens that bot-day's logs
    pg.locator("#trk-body tr").first.click(); pg.wait_for_timeout(900)
    chk("row_opens_logs", pg.input_value("#filter-robot") != "")

    # ---- no assignments: say what to add, invent nothing ----
    p2 = br.new_page(viewport={"width": 1440, "height": 900})
    H.watch_errors(p2, errs)
    p2.goto(url); H.seed(p2, observations=obs, assignments=[]); H.login(p2)
    p2.click("#tab-tracker"); p2.wait_for_timeout(900)
    chk("empty_names_assignments", "Assignments" in p2.inner_text("#trk-empty"))
    chk("empty_has_no_rows", p2.eval_on_selector_all("#trk-body tr", "e => e.length") == 0)

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
