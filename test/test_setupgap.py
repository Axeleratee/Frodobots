"""A low percentage caused by missing SETUP must say so, not just show red.

Reproduces the user's real situation: one bot assigned, the team working
hard on nine others, and a dashboard reading 20%.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_gap.html")
D = {n: H.days_ago(n) for n in range(0, 35)}

# alwin owns Alpha only. The team logs plenty against six other bots.
asg = [H.assign("a1", H.CRIS, "Alpha", D[6])]
obs = []
for n in range(2, 12):
    for bot in ("Charlie", "Echo", "Fox", "Godzilla", "Hugo", "Igor"):
        obs.append(H.obs("%s%d" % (bot, n), D[n], bot, by=H.CRIS,
                         logged_at=H.days_ago(n - 2) + "T10:00:00Z"))
obs.append(H.obs("alpha1", D[6], "Alpha", by=H.CRIS,
                 logged_at=D[4] + "T10:00:00Z"))

with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(viewport={"width": 1440, "height": 1200})
    H.watch_errors(pg, errs)
    pg.goto(url); H.seed(pg, observations=obs, assignments=asg); H.login(pg)
    pg.click("#tab-performance"); pg.wait_for_timeout(1500)

    chk("banner_shown", pg.is_visible("#ops-setup"))
    b = pg.inner_text("#ops-setup")
    chk("banner_counts_bots", "1 of 7 bots" in b, "| %s" % b.replace("\n", " ")[:110])
    chk("banner_counts_lost_work", "60 observations" in b, "| the work that is not counted")
    chk("banner_names_them", "Charlie" in b and "Godzilla" in b)
    chk("banner_says_what_to_do", "Assignments" in b)

    # the rail must not list people who were never given anything
    rail = pg.inner_text("#ops-rail")
    chk("rail_hides_unassigned", "0 of 0" not in rail, "| %s" % rail.replace("\n", " ")[:80])
    chk("rail_counts_them_instead", "no robot assigned" in rail)

    pg.locator("#card-team-ops").screenshot(path="/tmp/claude-0/ops_gap.png")

    # Once every bot has an owner the banner must disappear on its own.
    pg.evaluate("""([uid, start]) => {
      const a = JSON.parse(localStorage.getItem('__mock_assignments'));
      ['Charlie','Echo','Fox','Godzilla','Hugo','Igor'].forEach((r, i) =>
        a.push({id: 'g'+i, user_id: uid, robot: r, starts_on: start,
                ends_on: null, created_at: start + 'T00:00:00Z', created_by: uid, note: null}));
      localStorage.setItem('__mock_assignments', JSON.stringify(a));
    }""", [H.CRIS, D[12]])
    pg.evaluate("() => loadAssignments()"); pg.wait_for_timeout(900)
    pg.click("#tab-performance"); pg.wait_for_timeout(900)
    chk("banner_clears_when_set_up", not pg.is_visible("#ops-setup"))
    chk("rail_shows_the_person_now", "0 of 0" not in pg.inner_text("#ops-rail")
        and "/" in pg.inner_text("#ops-rail").replace(" of ", "/"))

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
