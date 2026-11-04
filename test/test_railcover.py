"""The per-person bar separates own work from work a teammate covered."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_rail.html", config={"REST_DAYS": []})
D = {n: H.days_ago(n) for n in range(0, 12)}

# alwin owns Alpha for 5 reviewable days. He does 2; a teammate covers 1;
# 2 are untouched.
asg = [H.assign("a1", H.CRIS, "Alpha", D[6])]
obs = [
    H.obs("x1", D[6], "Alpha", by=H.CRIS),
    H.obs("x2", D[5], "Alpha", by=H.CRIS),
    H.obs("x3", D[4], "Alpha", by=H.ADMIN),     # covered
]

with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(viewport={"width": 1440, "height": 1100})
    H.watch_errors(pg, errs)
    pg.goto(url); H.seed(pg, observations=obs, assignments=asg); H.login(pg)
    pg.click("#tab-performance"); pg.wait_for_timeout(1400)

    row = pg.inner_text("#ops-rail")
    chk("shows_own_fraction", "2 of 5" in row, "| %s" % row.replace("\n", " ")[:90])
    chk("shows_covered_count", "+1 covered" in row, "| %s" % row.replace("\n", " ")[:90])
    chk("percent_is_own_work", "40%" in row, "| 2 of 5 is his own: %s" % row.replace("\n", " ")[:90])

    segs = pg.evaluate("""() => [...document.querySelectorAll('#ops-rail > div')]
        .filter(d => d.querySelector('div[style*="height:5px"]'))
        .map(d => [...d.querySelectorAll('div[style*="height:5px"] > div')]
            .map(x => ({w: x.style.width, op: x.style.opacity})))""")
    chk("two_segments", segs and len(segs[0]) == 2, "| %s" % segs)
    chk("own_segment_solid", segs[0][0]["op"] in ("", "1"), "| %s" % segs[0][0])
    chk("covered_segment_pale", float(segs[0][1]["op"]) < 0.5, "| %s" % segs[0][1])
    chk("bar_reaches_reviewed_total",
        round(float(segs[0][0]["w"].rstrip("%")) + float(segs[0][1]["w"].rstrip("%"))) == 60,
        "| 3 of 5 reviewed in total: %s" % segs[0])

    chk("explains_the_two_tones", "covered by a teammate" in pg.inner_text("#ops-rail-wrap")
        if pg.query_selector("#ops-rail-wrap") else
        "covered by a teammate" in pg.inner_text("#card-team-ops"),
        "| the legend has to say which is which")

    # Nobody covering: one solid segment only.
    p2 = br.new_page(viewport={"width": 1440, "height": 1000})
    H.watch_errors(p2, errs)
    p2.goto(url); H.seed(p2, observations=obs[:2], assignments=asg); H.login(p2)
    p2.click("#tab-performance"); p2.wait_for_timeout(1300)
    segs2 = p2.evaluate("""() => [...document.querySelectorAll('#ops-rail > div')]
        .filter(d => d.querySelector('div[style*="height:5px"]'))
        .map(d => d.querySelectorAll('div[style*="height:5px"] > div').length)""")
    chk("no_cover_means_one_segment", segs2 and segs2[0] == 1, "| %s" % segs2)
    chk("no_covered_note", "+0 covered" not in p2.inner_text("#ops-rail"))

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
