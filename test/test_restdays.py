"""Sundays are not shifts, so they are never owed and never a gap."""
import sys, pathlib, datetime
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_rest.html")

today = datetime.date.today()
start = today - datetime.timedelta(days=27)
asg = [H.assign("a1", H.CRIS, "Alpha", start.isoformat())]

with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(viewport={"width": 1440, "height": 1100})
    H.watch_errors(pg, errs)
    pg.goto(url); H.seed(pg, observations=[], assignments=asg); H.login(pg)

    chk("config_read", pg.evaluate("() => REST_DAYS") == [0], "| 0 = Sunday")
    chk("sunday_detected", pg.evaluate("() => isRestDay('2026-11-01')") is True,
        "| Nov 1 2026 is a Sunday")
    chk("monday_is_a_shift", pg.evaluate("() => isRestDay('2026-11-02')") is False)

    obl = pg.evaluate("([a,b]) => obligationsIn(a,b)",
                      [start.isoformat(), today.isoformat()])
    dows = sorted(set(datetime.date.fromisoformat(o["date"]).weekday() for o in obl))
    chk("no_sunday_obligations", 6 not in dows, "| python weekday 6 = Sunday; got %s" % dows)
    chk("other_days_still_owed", len(dows) == 6, "| Mon-Sat -> %d distinct days" % len(dows))

    # Count what a 4-week window should contain: every day but Sundays, up to
    # the newest arrived data.
    newest = datetime.date.fromisoformat(pg.evaluate("() => latestReviewableDate()"))
    expect = sum(1 for i in range((newest - start).days + 1)
                 if (start + datetime.timedelta(days=i)).weekday() != 6)
    chk("obligation_count_exact", len(obl) == expect, "| %d vs %d" % (len(obl), expect))

    bl = pg.evaluate("([a,b]) => coverageFor(a,b).backlog",
                     [start.isoformat(), today.isoformat()])
    chk("backlog_skips_sundays",
        all(datetime.date.fromisoformat(b["date"]).weekday() != 6 for b in bl))

    pg.click("#tab-performance"); pg.wait_for_timeout(1300)
    chk("note_says_so", "Sundays are not counted" in pg.inner_text("#ops-note"),
        "| %s" % pg.inner_text("#ops-note")[-90:])

    # the date overview table must not list Sundays either
    pg.click("#tab-logs"); pg.wait_for_timeout(1000)
    sund = pg.evaluate("""() => [...document.querySelectorAll('#dt-body tr')]
        .map(r => r.dataset.date)
        .filter(d => new Date(d + 'T00:00:00').getDay() === 0)""")
    chk("table_skips_sundays", sund == [], "| %s" % sund)

    # The tracker derives its rows from the same obligations, so no Sunday
    # can appear there either.
    pg.click("#tab-tracker"); pg.wait_for_timeout(1000)
    sund_trk = pg.evaluate("""() => allExpected().map(r => r.obs_date)
        .filter(d => new Date(d + 'T00:00:00').getDay() === 0)""")
    chk("tracker_skips_sundays", sund_trk == [], "| %s" % sund_trk)
    chk("tracker_has_rows", pg.evaluate("() => allExpected().length") > 0)

    # A team that works every day must be unaffected.
    url7 = H.build("app_rest7.html", config={"REST_DAYS": []})
    p2 = br.new_page(viewport={"width": 1440, "height": 900})
    H.watch_errors(p2, errs)
    p2.goto(url7); H.seed(p2, observations=[], assignments=asg); H.login(p2)
    obl7 = p2.evaluate("([a,b]) => obligationsIn(a,b).length",
                       [start.isoformat(), today.isoformat()])
    chk("seven_day_team_unaffected", obl7 > len(obl), "| %d vs %d" % (obl7, len(obl)))
    p2.click("#tab-performance"); p2.wait_for_timeout(1100)
    chk("no_rest_note_when_none", "not counted — no shift" not in p2.inner_text("#ops-note"))

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
