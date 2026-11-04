"""One reviewer covering another's bot: the work is done, and it shows who."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_cover.html", config={"REST_DAYS": []})
D = {n: H.days_ago(n) for n in range(0, 10)}

# Charlie is cris's. Alpha is cris's too, and he does that one himself.
asg = [H.assign("a1", H.CRIS, "Charlie", D[7]), H.assign("a2", H.CRIS, "Alpha", D[7])]
obs = [
    H.obs("c1", D[5], "Charlie", by=H.ADMIN),     # boss covered for cris
    H.obs("c2", D[4], "Alpha",   by=H.CRIS),      # cris did his own
    H.obs("c3", D[3], "Charlie", by=H.CRIS),      # cris did his own
    H.obs("c4", D[3], "Charlie", by=H.ADMIN),     # ...and boss also logged it
]

def row(pg, date, bot):
    return pg.evaluate("""([d,b]) => {
        const r = allExpected().find(x => x.obs_date === d && x.robot === b);
        return r ? {status: r.status, own: r.ownWork, by: r.coveredBy} : null; }""", [date, bot])

with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(viewport={"width": 1440, "height": 1100})
    H.watch_errors(pg, errs)
    pg.goto(url); H.seed(pg, observations=obs, assignments=asg); H.login(pg)

    covered = row(pg, D[5], "Charlie")
    chk("covered_is_done", covered["status"] == "done",
        "| the data really was reviewed: %s" % covered)
    chk("covered_is_flagged", covered["by"] == "boss", "| %s" % covered)
    chk("covered_is_not_own_work", covered["own"] is False)

    own = row(pg, D[4], "Alpha")
    chk("own_work_is_done", own["status"] == "done")
    chk("own_work_not_flagged", own["by"] is None, "| %s" % own)

    both = row(pg, D[3], "Charlie")
    chk("owner_logged_too_is_not_covered", both["by"] is None,
        "| the owner did log it, so there is no stand-in to report: %s" % both)

    nothing = row(pg, D[6], "Charlie")
    chk("unlogged_still_pending", nothing["status"] == "pending")

    # on screen
    pg.click("#tab-tracker"); pg.wait_for_timeout(1000)
    txt = pg.evaluate("""([d]) => {
        const tr = [...document.querySelectorAll('#trk-body tr')]
          .find(r => r.dataset.date === d && r.dataset.bot === 'Charlie');
        return tr ? tr.innerText.replace(/\\\\n/g, ' | ') : null; }""", [D[5]])
    chk("tracker_shows_done", "Done" in txt, "| %s" % txt)
    chk("tracker_names_the_standin", "by boss" in txt, "| %s" % txt)

    pg.click("#tab-logs"); pg.wait_for_timeout(1100)
    dtxt = pg.evaluate("""([d]) => {
        const tr = [...document.querySelectorAll('#dt-body tr')]
          .find(r => r.dataset.date === d && r.dataset.bot === 'Charlie');
        return tr ? tr.innerText.replace(/\\\\n/g, ' | ') : null; }""", [D[5]])
    chk("overview_shows_done", "Done" in dtxt, "| %s" % dtxt)
    chk("overview_names_the_standin", "boss" in dtxt and "cris" in dtxt,
        "| the owner and who actually did it: %s" % dtxt)
    chk("overview_counts_it", "Covered by a teammate" in pg.inner_text("#dates-secondary"),
        "| %s" % pg.inner_text("#dates-secondary"))

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
