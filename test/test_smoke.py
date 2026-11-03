"""Baseline: the app still works untouched. Run this before and after changes."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build()

with sync_playwright() as pw:
    br = pw.chromium.launch()
    pg = br.new_page(viewport={"width": 1400, "height": 1000})
    H.watch_errors(pg, errs)
    pg.goto(url)
    H.seed(pg, observations=[
        H.obs("o1", H.days_ago(1), "Alpha"),
        H.obs("o2", H.days_ago(1), "Charlie", by=H.CRIS),
        H.obs("o3", H.days_ago(2), "Alpha", no_data=True),
        H.obs("o4", H.days_ago(3), "Echo", late=True),
    ])
    H.login(pg)

    chk("app_loads", pg.is_visible("#card-log"))
    chk("entries_loaded", pg.evaluate("() => entries.length") == 4,
        "| %d" % pg.evaluate("() => entries.length"))
    pg.click("#tab-logs"); pg.wait_for_timeout(700)
    chk("table_rows", pg.eval_on_selector_all("#table-body tr[data-row]", "e => e.length") == 4)
    chk("heatmap", pg.eval_on_selector_all("#dates-heatmap .hm-cell", "e => e.length") > 0)
    pg.click("#dates-view-bot"); pg.wait_for_timeout(900)
    chk("matrix", pg.eval_on_selector_all("#dates-matrix .hm-cell", "e => e.length") > 0)
    pg.click("#tab-settings"); pg.wait_for_timeout(500)
    chk("options_card_admin", pg.is_visible("#card-options"))
    pg.click("#tab-performance"); pg.wait_for_timeout(900)
    chk("performance_tab", pg.is_visible("#page-performance"))
    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
