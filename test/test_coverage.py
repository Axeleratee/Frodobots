"""The coverage engine. Numbers here drive how a person is judged, so every
rule gets an explicit case."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_cov.html", config={"REVIEW_DELAY_DAYS": 0})

D = {n: H.days_ago(n) for n in range(0, 12)}

# cris owns Alpha for the last 5 days (D4..D0 = 5 bot-days).
#   D4 checked by cris      -> done
#   D3 checked by cris, no data logged -> still done, he looked
#   D2 checked by BOSS      -> coveredByOther
#   D1 nobody               -> missed  (backlog)
#   D0 checked by cris      -> done
# boss owns Fox for the last 2 days, checks neither -> 0%
obs = [
    H.obs("c4", D[4], "Alpha", by=H.CRIS),
    H.obs("c3", D[3], "Alpha", by=H.CRIS, no_data=True),
    H.obs("b2", D[2], "Alpha", by=H.ADMIN),
    H.obs("c0", D[0], "Alpha", by=H.CRIS),
    # outside any assignment: must not inflate anyone's coverage
    H.obs("x1", D[1], "Kilo", by=H.CRIS),
    # logged 3 days after the observation date -> turnaround 3
    H.obs("c9", D[9], "Charlie", by=H.CRIS, logged_at=D[6] + "T10:00:00Z"),
]
asg = [
    H.assign("a1", H.CRIS, "Alpha", D[4]),
    H.assign("a2", H.ADMIN, "Fox", D[1]),
    # an assignment that ended before the window: must contribute nothing
    H.assign("a3", H.CRIS, "Echo", D[11], D[10]),
]

with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(viewport={"width": 1400, "height": 1000})
    H.watch_errors(pg, errs)
    pg.goto(url); H.seed(pg, observations=obs, assignments=asg); H.login(pg)

    cov = pg.evaluate("([a,b]) => coverageFor(a,b)", [D[4], D[0]])
    rows = {r["username"]: r for r in cov["rows"]}
    print("  cris:", {k: rows["cris"][k] for k in
                      ("assigned", "done", "coveredByOther", "missed", "coverage")})
    print("  boss:", {k: rows["boss"][k] for k in
                      ("assigned", "done", "coveredByOther", "missed", "coverage")})

    chk("assigned_counts_days", rows["cris"]["assigned"] == 5, "| %d" % rows["cris"]["assigned"])
    chk("no_data_counts_as_checked", rows["cris"]["done"] == 3,
        "| D4, D3(no data), D0 -> %d" % rows["cris"]["done"])
    chk("other_person_not_counted_as_mine", rows["cris"]["coveredByOther"] == 1)
    chk("only_true_gap_is_missed", rows["cris"]["missed"] == 1)
    chk("coverage_is_own_work", rows["cris"]["coverage"] == 60, "| 3/5 -> %s" % rows["cris"]["coverage"])
    chk("unassigned_work_does_not_inflate", rows["cris"]["assigned"] == 5,
        "| the Kilo row is outside every assignment")
    chk("ended_assignment_excluded", "Echo" not in [b["robot"] for b in cov["backlog"]])

    chk("boss_zero", rows["boss"]["assigned"] == 2 and rows["boss"]["done"] == 0
        and rows["boss"]["coverage"] == 0)

    chk("team_coverage_counts_any_checker", cov["coverage"] == 57,
        "| 4 of 7 bot-days checked by someone -> %s" % cov["coverage"])

    bl = cov["backlog"]
    chk("backlog_lists_only_real_gaps", len(bl) == 3, "| %s" % [(b["robot"], b["date"]) for b in bl])
    chk("backlog_oldest_first", bl == sorted(bl, key=lambda b: (b["date"], b["robot"])))

    # future work is not a miss
    fut = pg.evaluate("([a,b]) => obligationsIn(a,b).length", [D[0], H.days_ago(-5)])
    chk("future_dates_not_due", fut == 2, "| Alpha + Fox today only -> %d" % fut)

    # turnaround
    t = pg.evaluate("() => turnaroundDays(entries.find(e => e.id === 'c9'))")
    chk("turnaround_measured", t == 3, "| %s" % t)
    chk("turnaround_ignores_same_day",
        pg.evaluate("() => turnaroundDays(entries.find(e => e.id === 'c4'))") == 0)
    chk("median_resists_outlier", pg.evaluate("() => median([1,1,1,1,40])") == 1)
    chk("median_even_length", pg.evaluate("() => median([2,4])") == 3)
    chk("median_empty_is_null", pg.evaluate("() => median([]) === null"))

    # week / month boundaries
    wk = pg.evaluate("() => weekRange('2026-11-03')")   # a Tuesday
    chk("week_starts_monday", wk["from"] == "2026-11-02" and wk["to"] == "2026-11-08", "| %s" % wk)
    mo = pg.evaluate("() => monthRange('2026-11-03')")
    chk("month_range", mo["from"] == "2026-11-01" and mo["to"] == "2026-11-30", "| %s" % mo)
    chk("month_handles_february",
        pg.evaluate("() => monthRange('2028-02-10').to") == "2028-02-29", "| leap year")

    # no assignments at all -> null, never a misleading 0%
    pg2 = br.new_page()
    H.watch_errors(pg2, errs)
    pg2.goto(url); H.seed(pg2, observations=obs, assignments=[]); H.login(pg2)
    c2 = pg2.evaluate("([a,b]) => coverageFor(a,b)", [D[4], D[0]])
    chk("no_assignments_is_null_not_zero", c2["coverage"] is None, "| %s" % c2["coverage"])

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
