"""Data that arrives AFTER the first render must still reach every screen.

The date table rendered once at startup and was never rebuilt when the
assignments finished loading, so the HBA reviewer column stayed empty for
the whole session. These tests pin each loader to the views it feeds.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_late.html")
D = {n: H.days_ago(n) for n in range(0, 12)}

asg = [H.assign("a1", H.CRIS, "Alpha", D[8]), H.assign("a2", H.ADMIN, "Echo", D[8])]
obs = [H.obs("o%d" % n, D[n], "Alpha", by=H.CRIS) for n in range(2, 8)]
tasks = [H.task("k1", D[4], "Alpha", H.CRIS, "completed", D[2] + "T09:00:00Z")]

def reviewers(page):
    return page.evaluate("""() => [...document.querySelectorAll('#dt-body tr td:nth-child(2)')]
        .map(td => td.textContent.trim())""")

with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(viewport={"width": 1440, "height": 1100})
    H.watch_errors(pg, errs)
    pg.goto(url); H.seed(pg, observations=obs, assignments=asg, tasks=tasks); H.login(pg)
    pg.click("#tab-logs"); pg.wait_for_timeout(1100)

    named = [r for r in reviewers(pg) if r and r != "—"]
    chk("reviewer_column_filled", len(named) > 0, "| %s" % reviewers(pg)[:6])

    # Simulate the real order: the table renders before assignments arrive.
    pg.evaluate("() => { _assignments = []; renderDateTable(); }")
    pg.wait_for_timeout(300)
    # One row keeps its reviewer with no assignments at all: it comes from the
    # review task, which names a reviewer of its own. Everything else blanks.
    named_now = [r for r in reviewers(pg) if r and r != "\u2014"]
    chk("blank_without_assignments", len(named_now) == 1,
        "| only the task-backed row keeps a name: %s" % reviewers(pg)[:5])

    # loadAssignments alone must bring the table back - no extra render call.
    pg.evaluate("() => loadAssignments()"); pg.wait_for_timeout(800)
    chk("loadAssignments_refreshes_table",
        any(r and r != "—" for r in reviewers(pg)), "| %s" % reviewers(pg)[:6])
    chk("loadAssignments_refreshes_cards",
        pg.evaluate("() => dtCounts(dtRows()).total") > 0)

    # loadTasks alone must bring review status back.
    pg.evaluate("() => { _tasks = []; renderDateTable(); }"); pg.wait_for_timeout(300)
    chk("no_status_without_tasks", "Completed" not in pg.inner_text("#dt-body"))
    pg.evaluate("() => loadTasks()"); pg.wait_for_timeout(800)
    chk("loadTasks_refreshes_table", "Completed" in pg.inner_text("#dt-body"))

    # loadTeam alone must resolve the names.
    pg.evaluate("() => { _team = []; _teamById = {}; renderDateTable(); }"); pg.wait_for_timeout(300)
    chk("blank_names_without_roster",
        all(r == "—" for r in reviewers(pg)), "| %s" % reviewers(pg)[:4])
    pg.evaluate("() => loadTeam()"); pg.wait_for_timeout(800)
    chk("loadTeam_refreshes_table",
        any(r and r != "—" for r in reviewers(pg)), "| %s" % reviewers(pg)[:6])

    # ...and the other screens fed by the same data.
    pg.click("#tab-performance"); pg.wait_for_timeout(1000)
    chk("ops_has_rail", "of" in pg.inner_text("#ops-rail"))
    pg.evaluate("() => { _assignments = []; renderTeamOps(); }"); pg.wait_for_timeout(300)
    pg.evaluate("() => loadAssignments()"); pg.wait_for_timeout(900)
    chk("loadAssignments_refreshes_dashboard",
        "of" in pg.inner_text("#ops-rail"), "| %s" % pg.inner_text("#ops-rail")[:60])

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
