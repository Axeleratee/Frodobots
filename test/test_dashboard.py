"""The team dashboard renders the engine's numbers honestly."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build()
D = {n: H.days_ago(n) for n in range(0, 40)}

obs, asg = [], [
    H.assign("a1", H.CRIS, "Alpha", D[25]),
    H.assign("a2", H.CRIS, "Charlie", D[25]),
    H.assign("a3", H.ADMIN, "Echo", D[25]),
]
# cris keeps Alpha current but neglects Charlie; boss keeps Echo except lately.
for n in range(0, 26):
    if n % 5:
        obs.append(H.obs("al%d" % n, D[n], "Alpha", by=H.CRIS))
    if n % 2 == 0:
        obs.append(H.obs("ch%d" % n, D[n], "Charlie", by=H.CRIS, no_data=(n % 6 == 0)))
    if n > 3:
        obs.append(H.obs("ec%d" % n, D[n], "Echo", by=H.ADMIN))

with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(viewport={"width": 1400, "height": 1200})
    H.watch_errors(pg, errs)
    pg.goto(url); H.seed(pg, observations=obs, assignments=asg); H.login(pg)
    pg.click("#tab-performance"); pg.wait_for_timeout(1500)

    chk("card_visible", pg.is_visible("#card-team-ops"))
    chk("three_windows", pg.eval_on_selector_all("#ops-windows > div", "e => e.length") == 3)
    txt = pg.inner_text("#ops-windows")
    chk("windows_labelled", all(w in txt for w in ("TODAY", "THIS WEEK", "THIS MONTH")))
    chk("denominator_shown", "bot-days checked" in txt, "| never a bare percentage")
    chk("turnaround_shown", "Turnaround" in txt)

    chk("rail_has_members", pg.eval_on_selector_all("#ops-rail > div", "e => e.length") == 2)
    rail = pg.inner_text("#ops-rail")
    chk("rail_shows_fraction", "/" in rail, "| %s" % rail.replace("\n", " ")[:80])
    chk("rail_worst_first", pg.evaluate("""() => {
        const v = [...document.querySelectorAll('#ops-rail > div')]
          .map(d => parseInt((d.innerText.match(/(\\d+)%/) || [0, 999])[1], 10));
        return v.every((x, i) => i === 0 || v[i-1] <= x);
      }"""), "| a dashboard opens on what needs attention")

    chk("backlog_listed", pg.eval_on_selector_all("#ops-backlog .ops-bl", "e => e.length") > 0)
    chk("backlog_oldest_first", pg.evaluate("""() => {
        const d = [...document.querySelectorAll('#ops-backlog .ops-bl')].map(b => b.dataset.date);
        return d.every((x, i) => i === 0 || d[i-1] <= x);
      }"""))
    chk("trend_drawn", pg.eval_on_selector_all("#ops-trend > div:first-child > div", "e => e.length") == 12)

    # backlog click must land on that bot + that date
    first = pg.locator("#ops-backlog .ops-bl").first
    bot, date = first.get_attribute("data-bot"), first.get_attribute("data-date")
    first.click(); pg.wait_for_timeout(900)
    chk("backlog_click_filters",
        pg.input_value("#filter-robot") == bot and pg.input_value("#filter-from") == date,
        "| %s %s" % (bot, date))

    # window control
    pg.click("#tab-performance"); pg.wait_for_timeout(900)
    many = pg.eval_on_selector_all("#ops-backlog .ops-bl", "e => e.length")
    pg.select_option("#ops-backlog-window", "7"); pg.wait_for_timeout(700)
    few = pg.eval_on_selector_all("#ops-backlog .ops-bl", "e => e.length")
    chk("window_narrows_backlog", few <= many, "| 30d=%d 7d=%d" % (many, few))

    pg.locator("#card-team-ops").screenshot(path="/tmp/claude-0/ops.png")

    # Empty state: no assignments must never read as 0% failure
    pg2 = br.new_page(viewport={"width": 1400, "height": 1200})
    H.watch_errors(pg2, errs)
    pg2.goto(url); H.seed(pg2, observations=obs, assignments=[]); H.login(pg2)
    pg2.click("#tab-performance"); pg2.wait_for_timeout(1200)
    t2 = pg2.inner_text("#ops-windows")
    chk("no_assignments_not_zero", "nothing assigned" in t2 and "0%" not in t2, "| %s" % t2.replace("\n", " ")[:70])
    chk("backlog_explains_setup", "Assign robots" in pg2.inner_text("#ops-backlog"))
    chk("trend_explains_setup", "once robots have been assigned" in pg2.inner_text("#ops-trend"))

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
