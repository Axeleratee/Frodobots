"""Upload status: checked-and-empty is not the same as nobody-looked."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_up.html")
D = {n: H.days_ago(n) for n in range(0, 12)}
asg = [H.assign("a1", H.CRIS, "Alpha", D[9])]

obs = [
    H.obs("u1", D[7], "Alpha", by=H.CRIS),                 # arrived, on time
    H.obs("u2", D[6], "Alpha", by=H.CRIS, late=True),      # arrived, late
    H.obs("u3", D[5], "Alpha", by=H.CRIS, no_data=True),   # checked, nothing there
    # D[4] has nothing at all -> nobody looked
    # a day with BOTH a real log and a no-data log still counts as arrived
    H.obs("u4", D[3], "Alpha", by=H.CRIS, no_data=True),
    H.obs("u5", D[3], "Alpha", by=H.CRIS),
]

with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(viewport={"width": 1440, "height": 1100})
    H.watch_errors(pg, errs)
    pg.goto(url); H.seed(pg, observations=obs, assignments=asg); H.login(pg)
    pg.click("#tab-logs"); pg.wait_for_timeout(1100)

    def up(date):
        return pg.evaluate("""([d]) => {
            const r = botDayRows(d, d).find(x => x.robot === 'Alpha');
            return r ? r.uploadStatus : null; }""", [date])

    chk("arrived_on_time", up(D[7]) == "ontime", "| %s" % up(D[7]))
    chk("arrived_late", up(D[6]) == "late", "| %s" % up(D[6]))
    chk("checked_but_empty_is_nodata", up(D[5]) == "nodata",
        "| the reviewer looked: %s" % up(D[5]))
    chk("nobody_looked_is_missing", up(D[4]) == "missing", "| %s" % up(D[4]))
    chk("real_data_beats_a_nodata_entry", up(D[3]) == "ontime",
        "| one real log on the day is enough: %s" % up(D[3]))

    # The two must read differently on screen, and only one of them is red.
    txt = pg.inner_text("#dt-body")
    chk("labels_differ", "No data" in txt and "Not logged" in txt, "| %s" % txt[:120])
    colors = pg.evaluate("""() => {
        const out = {};
        document.querySelectorAll('#dt-body tr').forEach(tr => {
          const b = tr.querySelector('td:nth-child(5) span');
          if (b) out[b.textContent.trim()] = getComputedStyle(b).color;
        });
        return out; }""")
    chk("nodata_is_not_red", colors.get("No data") != colors.get("Not logged"),
        "| %s" % colors)

    # Cards must separate them too.
    cards = pg.inner_text("#dates-cards")
    chk("card_no_data", "NO DATA" in cards and "checked, none arrived" in cards)
    chk("card_not_logged", "NOT LOGGED" in cards and "nobody looked yet" in cards)
    counts = pg.evaluate("() => { const c = dtCounts(dtRows()); return [c.nodata, c.missing]; }")
    chk("counts_separate", counts[0] >= 1 and counts[1] >= 1, "| nodata=%d missing=%d" % tuple(counts))

    # Filters distinguish them.
    pg.select_option("#dt-upload", "nodata"); pg.wait_for_timeout(600)
    chk("filter_nodata", pg.evaluate("""() => [...document.querySelectorAll('#dt-body tr')]
        .every(r => r.innerText.includes('No data'))"""))
    pg.select_option("#dt-upload", "missing"); pg.wait_for_timeout(600)
    chk("filter_missing", pg.evaluate("""() => [...document.querySelectorAll('#dt-body tr')]
        .every(r => r.innerText.includes('Not logged'))"""))
    pg.select_option("#dt-upload", ""); pg.wait_for_timeout(400)

    # Coverage must still treat "no data" as checked - that rule is unchanged.
    c = pg.evaluate("([a,b]) => coverageFor(a,b)", [D[9], D[0]])
    chk("coverage_still_counts_nodata_as_checked",
        any(b["date"] != D[5] for b in c["backlog"]) and
        all(b["date"] != D[5] for b in c["backlog"]),
        "| D5 was checked, so it is not in the backlog")

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
