"""Catching up history: close only the reviews that really have logs."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_catch.html")
D = {n: H.days_ago(n) for n in range(0, 12)}
asg = [H.assign("a1", H.ADMIN, "Alpha", D[9]), H.assign("a2", H.CRIS, "Echo", D[9])]

# Four open reviews. Two have an entry behind them, two have nothing at all.
tasks = [
    H.task("t1", D[7], "Alpha", H.ADMIN, "pending"),   # has a log
    H.task("t2", D[6], "Alpha", H.ADMIN, "pending"),   # has a "no data" log
    H.task("t3", D[5], "Alpha", H.ADMIN, "pending"),   # nothing logged
    H.task("t4", D[4], "Echo",  H.CRIS,  "pending"),   # has a log, but not mine
]
obs = [
    H.obs("o1", D[7], "Alpha", by=H.ADMIN),
    H.obs("o2", D[6], "Alpha", by=H.ADMIN, no_data=True),
    H.obs("o3", D[4], "Echo",  by=H.CRIS),
]

def st(pg, tid):
    return pg.evaluate("([i]) => (_tasks.find(t => t.id === i) || {}).status", [tid])

with sync_playwright() as pw:
    br = pw.chromium.launch()
    pg = br.new_page(viewport={"width": 1440, "height": 1100})
    H.watch_errors(pg, errs); pg.on("dialog", lambda d: d.accept())
    pg.goto(url); H.seed(pg, observations=obs, assignments=asg, tasks=tasks); H.login(pg)
    pg.click("#tab-tracker"); pg.wait_for_timeout(1000)

    chk("offered", pg.is_visible("#trk-catchup"))
    chk("counts_only_logged", "3" in pg.inner_text("#trk-catchup"),
        "| t1, t2 and t4 have logs; t3 does not: %s" % pg.inner_text("#trk-catchup"))

    pg.click("#trk-catchup"); pg.wait_for_timeout(1800)
    chk("closed_the_logged_one", st(pg, "t1") == "completed")
    chk("nodata_counts_as_logged", st(pg, "t2") == "completed",
        "| the reviewer looked and said nothing arrived")
    chk("left_the_unlogged_one", st(pg, "t3") == "pending",
        "| nothing was logged, so nothing is claimed: %s" % st(pg, "t3"))
    chk("closed_other_peoples_as_admin", st(pg, "t4") == "completed")
    chk("button_hides_when_done", not pg.is_visible("#trk-catchup"))

    # It must obey the filters, like the other bulk action.
    pg2 = br.new_page(viewport={"width": 1440, "height": 1100})
    H.watch_errors(pg2, errs); pg2.on("dialog", lambda d: d.accept())
    pg2.goto(url); H.seed(pg2, observations=obs, assignments=asg, tasks=tasks); H.login(pg2)
    pg2.click("#tab-tracker"); pg2.wait_for_timeout(1000)
    pg2.select_option("#trk-f-robot", "Echo"); pg2.wait_for_timeout(700)
    chk("respects_filters", "1" in pg2.inner_text("#trk-catchup"),
        "| %s" % pg2.inner_text("#trk-catchup"))
    pg2.click("#trk-catchup"); pg2.wait_for_timeout(1500)
    chk("filtered_run_closed_only_that", st(pg2, "t4") == "completed" and st(pg2, "t1") == "pending")
    pg2.close()

    # An editor may only close their own.
    pg3 = br.new_page(viewport={"width": 1440, "height": 1100})
    H.watch_errors(pg3, errs); pg3.on("dialog", lambda d: d.accept())
    pg3.goto(url); H.seed(pg3, observations=obs, assignments=asg, tasks=tasks); H.login(pg3, "cris")
    pg3.click("#tab-tracker"); pg3.wait_for_timeout(1000)
    chk("editor_sees_only_own", "1" in pg3.inner_text("#trk-catchup"),
        "| %s" % pg3.inner_text("#trk-catchup"))
    pg3.click("#trk-catchup"); pg3.wait_for_timeout(1500)
    chk("editor_closed_own", st(pg3, "t4") == "completed")
    chk("editor_left_others", st(pg3, "t1") == "pending")
    pg3.close()

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
