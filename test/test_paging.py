"""Past 1,000 rows: every observation must survive a reload (Supabase caps a response)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_paging.html", config={"REST_DAYS": [], "REVIEW_DELAY_DAYS": 0})
D = {n: H.days_ago(n) for n in range(0, 400)}
BOTS = ["Alpha", "Charlie", "Echo", "Fox", "Godzilla", "Hugo", "Igor", "Jackie", "Kilo"]

N = 1250
obs = []
for i in range(N):
    d = D[399 - (i * 399 // N)]            # oldest first, the way they were written
    o = H.obs("P%04d" % i, d, BOTS[i % 9], logged_at=d + "T%02d:%02d:00Z" % (i % 24, i % 60))
    obs.append(o)
# The newest log: the one that used to vanish.
obs.append(H.obs("NEWEST", D[0], "Fox", logged_at=D[0] + "T23:59:00Z"))
late_events = [H.late_event("E%04d" % i, "P%04d" % i, "unresolved", D[1] + "T%02d:00:00Z" % (i % 24)) for i in range(1100)]

def load(pg, max_rows=None):
    pg.goto(url); H.seed(pg, observations=obs, late_events=late_events)
    if max_rows:
        pg.evaluate("n => localStorage.setItem('__mock_max_rows', String(n))", max_rows)
    H.login(pg); pg.wait_for_timeout(1500)

with sync_playwright() as pw:
    br = pw.chromium.launch()

    pg = br.new_page(viewport={"width": 1400, "height": 1000})
    H.watch_errors(pg, errs); pg.on("dialog", lambda d: d.accept())
    load(pg)
    n = pg.evaluate("() => entries.length")
    chk("all_observations_loaded", n == N + 1, "| %d of %d" % (n, N + 1))
    chk("newest_present", pg.evaluate("() => entries.some(e => e.id === 'NEWEST')"))
    chk("no_duplicates", pg.evaluate("() => new Set(entries.map(e => e.id)).size === entries.length"))
    chk("late_events_all_loaded", pg.evaluate("() => _lateEvents.length") == 1100,
        "| %d" % pg.evaluate("() => _lateEvents.length"))

    # The status the user saw: today's Fox must read Done, not "Not logged".
    st = pg.evaluate("""() => { const r = botDayRows(localToday(), localToday()).find(x => x.robot === 'Fox');
                                return r ? r.uploadStatus : 'none'; }""")
    chk("newest_counts_in_overview", st in ("ontime", "late"), "| %s" % st)

    # Save a new one, reload: it must still be there.
    pg.evaluate("""() => {
        document.getElementById('f-date').value = localToday();
        document.getElementById('f-robot').value = 'Hugo';
    }""")
    pg.evaluate("() => { taskMS.set ? taskMS.set(['sweep floor']) : null; }")
    saved = pg.evaluate("""async () => {
        const e = await dbAdd({ date: localToday(), robot: 'Hugo', task: ['sweep floor'], issue: ['none'],
                                severity: 0, notes: 'saved after 1250', links: [], noData: false, lateUpload: false });
        return e && e.id;
    }""")
    pg.reload(); H.login(pg); pg.wait_for_timeout(1500)
    chk("saved_survives_reload", pg.evaluate("id => entries.some(e => e.id === id)", saved),
        "| the reported bug: logged, then gone after refresh")
    chk("count_after_save", pg.evaluate("() => entries.length") == N + 2)
    pg.close()

    # A server set to a smaller cap must still yield everything.
    p2 = br.new_page(viewport={"width": 1200, "height": 900}); H.watch_errors(p2, errs)
    load(p2, max_rows=300)
    n2 = p2.evaluate("() => entries.length")
    chk("smaller_server_cap_still_complete", n2 == N + 1, "| %d" % n2)
    p2.close()

    chk("no_js_errors", not errs, "|%s" % errs[:3])
    br.close()

sys.exit(chk.report())
