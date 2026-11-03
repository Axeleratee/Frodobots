"""The pipeline delay: nothing is missing, and nobody is late, before the
cleaned data has actually reached the team."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build()
D = {n: H.days_ago(n) for n in range(0, 15)}

# cris owns Alpha for the last 8 days and has reviewed NOTHING.
asg = [H.assign("a1", H.CRIS, "Alpha", D[8])]

with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(viewport={"width": 1400, "height": 1200})
    H.watch_errors(pg, errs)
    pg.goto(url); H.seed(pg, observations=[], assignments=asg); H.login(pg)

    chk("delay_read_from_config", pg.evaluate("() => REVIEW_DELAY_DAYS") == 2)
    chk("latest_reviewable_is_two_days_back",
        pg.evaluate("() => latestReviewableDate()") == D[2], "| %s" % D[2])

    # D8..D2 are due (7 days). D1 and D0 have not arrived yet.
    obl = pg.evaluate("([a,b]) => obligationsIn(a,b)", [D[8], D[0]])
    dates = sorted(set(o["date"] for o in obl))
    chk("todays_data_not_due_yet", D[0] not in dates, "| today's data cannot be reviewed today")
    chk("yesterdays_data_not_due_yet", D[1] not in dates)
    chk("two_days_back_is_due", D[2] in dates)
    chk("due_count", len(obl) == 7, "| D8..D2 -> %d" % len(obl))

    c = pg.evaluate("([a,b]) => coverageFor(a,b)", [D[8], D[0]])
    chk("backlog_excludes_unarrived",
        all(b["date"] <= D[2] for b in c["backlog"]), "| %s" % [b["date"] for b in c["backlog"]])

    # Turnaround is measured from arrival, so the fastest possible is 0.
    pg2 = br.new_page()
    H.watch_errors(pg2, errs)
    obs = [
        # reviewed the day it arrived -> 0, not 2
        H.obs("fast", D[6], "Alpha", by=H.CRIS, logged_at=D[4] + "T09:00:00Z"),
        # reviewed three days after arrival -> 3
        H.obs("slow", D[8], "Alpha", by=H.CRIS, logged_at=D[3] + "T09:00:00Z"),
        # arrived early somehow -> credited as 0, never negative
        H.obs("early", D[5], "Alpha", by=H.CRIS, logged_at=D[5] + "T09:00:00Z"),
    ]
    pg2.goto(url); H.seed(pg2, observations=obs, assignments=asg); H.login(pg2)
    t = pg2.evaluate("""() => Object.fromEntries(
        entries.map(e => [e.id, turnaroundDays(e)]))""")
    chk("pipeline_lag_not_charged", t["fast"] == 0, "| reviewed on arrival -> %s" % t["fast"])
    chk("real_lateness_counted", t["slow"] == 3, "| %s" % t["slow"])
    chk("never_negative", t["early"] == 0, "| %s" % t["early"])

    pg2.click("#tab-performance"); pg2.wait_for_timeout(1400)
    note = pg2.inner_text("#ops-note")
    chk("delay_explained_on_screen", "2 days" in note and "arrives" in note,
        "| %s" % note[-90:])
    tiles = pg2.inner_text("#ops-windows")
    chk("first_tile_is_newest_arrived", "NEWEST DAY IN" in tiles)
    shown = pg2.evaluate("([d]) => plainDate(d)", [D[2]])
    chk("first_tile_dated", shown in tiles, "| tile should name %s" % shown)
    chk("asof_says_data_through", "data through" in pg2.inner_text("#ops-asof"))

    pg2.locator("#card-team-ops").screenshot(path="/tmp/claude-0/ops_delay.png")

    # A same-day team (delay 0) must get the old behaviour back untouched.
    url0 = H.build("app_nodelay.html", config={"REVIEW_DELAY_DAYS": 0})
    pg3 = br.new_page(viewport={"width": 1400, "height": 1200})
    H.watch_errors(pg3, errs)
    pg3.goto(url0); H.seed(pg3, observations=obs, assignments=asg); H.login(pg3)
    chk("zero_delay_read", pg3.evaluate("() => REVIEW_DELAY_DAYS") == 0)
    chk("zero_delay_today_is_due",
        pg3.evaluate("() => latestReviewableDate()") == D[0])
    o0 = pg3.evaluate("([a,b]) => obligationsIn(a,b).length", [D[8], D[0]])
    chk("zero_delay_counts_today", o0 == 9, "| D8..D0 -> %d" % o0)
    chk("zero_delay_turnaround_from_date",
        pg3.evaluate("() => turnaroundDays(entries.find(e => e.id === 'fast'))") == 2,
        "| with no pipeline, logging 2 days on really is 2 days")
    pg3.click("#tab-performance"); pg3.wait_for_timeout(1200)
    chk("zero_delay_tile_says_today", "TODAY" in pg3.inner_text("#ops-windows"))
    chk("zero_delay_note_omits_pipeline", "arrives" not in pg3.inner_text("#ops-note"))

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
