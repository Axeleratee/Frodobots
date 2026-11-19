"""Bot ranking on the Dashboard: counts, ties, metrics, periods, click-through."""
import sys, pathlib, datetime
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_ranking.html", config={"REST_DAYS": []})
D = {n: H.days_ago(n) for n in range(0, 120)}

obs = []
def add(bot, days, issue=False, no_data=False):
    for d in days:
        obs.append(H.obs("%s-%d-%d" % (bot, d, len(obs)), D[d], bot,
                         issues=("camera_blur",) if issue else ("none",), no_data=no_data))

# Inside the last 30 days:
add("Alpha",   [1, 2, 3, 4, 5, 6])            # 6 obs on 6 days, no issues
add("Echo",    [1, 1, 1, 2], issue=True)      # 4 obs, 4 issues, 2 days
add("Fox",     [3, 4, 5, 8])                  # 4 obs (ties Echo), 4 days
add("Fox",     [9, 10], no_data=True)         # 2 no-data: must not count
add("Hugo",    [2])                           # 1 obs
add("Hugo",    [6, 7, 8], no_data=True)       # only no-data otherwise
add("Zulu",    [3, 4])                        # typed-in bot, not in the list
# Outside 30 days (only "All time" sees these):
add("Charlie", [60, 61, 62, 63, 64, 65, 66, 67])   # 8 obs

def rows(pg):
    return pg.evaluate("""() => [...document.querySelectorAll('#rank-list .rank-row')].map(r => ({
        bot: r.dataset.bot,
        pos: r.querySelector('.rank-pos').textContent,
        val: +r.querySelector('.rank-val').textContent,
        meta: r.querySelector('.rank-meta').textContent }))""")

with sync_playwright() as pw:
    br = pw.chromium.launch()
    pg = br.new_page(viewport={"width": 1400, "height": 1000})
    H.watch_errors(pg, errs)
    pg.goto(url); H.seed(pg, observations=obs); H.login(pg); pg.wait_for_timeout(1000)

    chk("card_on_dashboard", pg.locator("#page-dashboard #card-rank").is_visible())
    chk("defaults", pg.input_value("#rank-metric") == "obs" and pg.input_value("#rank-period") == "30")

    # ---- observations, last 30 days ----
    r = rows(pg); top = [(x["bot"], x["pos"], x["val"]) for x in r[:5]]
    chk("order_obs", top == [("Alpha", "#1", 6), ("Echo", "#2", 4), ("Fox", "#2", 4), ("Zulu", "#4", 2), ("Hugo", "#5", 1)],
        "| %s" % top)
    fox = next(x for x in r if x["bot"] == "Fox")
    chk("nodata_not_counted_but_shown", fox["val"] == 4 and "2 no data" in fox["meta"], "| %s" % fox)
    hugo = next(x for x in r if x["bot"] == "Hugo")
    chk("hugo_only_one", hugo["val"] == 1 and "3 no data" in hugo["meta"], "| %s" % hugo)
    zero = [x for x in r if x["val"] == 0]
    chk("idle_bots_listed_at_bottom", [x["bot"] for x in r[-len(zero):]] == [x["bot"] for x in zero] and
        all(x["pos"] == "—" for x in zero) and "Charlie" in [x["bot"] for x in zero],
        "| %s" % [(x["bot"], x["pos"]) for x in zero])
    chk("typed_in_bot_appears", any(x["bot"] == "Zulu" for x in r))
    summ = pg.inner_text("#rank-summary")
    chk("summary_total_and_share", "17 observations across 5 bots" in summ and "Alpha (6, 35%)" in summ, "| %s" % summ)

    w = pg.evaluate("() => [...document.querySelectorAll('.rank-fill')].slice(0,3).map(f => f.style.width)")
    chk("bar_scaled_to_max", w[0] == "100%" and w[1] == "66.7%", "| %s" % w)

    # ---- issues found ----
    pg.select_option("#rank-metric", "issues"); pg.wait_for_timeout(250)
    r = rows(pg)
    chk("issues_order", (r[0]["bot"], r[0]["val"]) == ("Echo", 4) and r[1]["val"] == 0, "| %s" % r[:2])
    chk("issues_summary", "4 issues found across 1 bot" in pg.inner_text("#rank-summary"), "| %s" % pg.inner_text("#rank-summary"))

    # ---- days with data ----
    pg.select_option("#rank-metric", "days"); pg.wait_for_timeout(250)
    r = rows(pg); top = [(x["bot"], x["val"]) for x in r[:3]]
    chk("days_order", top == [("Alpha", 6), ("Fox", 4), ("Echo", 2)] or top == [("Alpha", 6), ("Fox", 4), ("Zulu", 2)],
        "| %s" % top)
    chk("days_summary_no_share", "%" not in pg.inner_text("#rank-summary") and "Alpha" in pg.inner_text("#rank-summary"))

    # ---- all time ----
    pg.select_option("#rank-metric", "obs"); pg.select_option("#rank-period", "all"); pg.wait_for_timeout(250)
    r = rows(pg)
    chk("all_time_includes_old", (r[0]["bot"], r[0]["val"]) == ("Charlie", 8), "| %s" % r[:2])

    # ---- this week starts Monday ----
    pg.select_option("#rank-period", "week"); pg.wait_for_timeout(250)
    today = datetime.date.fromisoformat(D[0])
    monday = today - datetime.timedelta(days=today.weekday())
    exp = sum(1 for o in obs if not o["entry"]["noData"] and monday.isoformat() <= o["entry"]["date"] <= D[0])
    got = sum(x["val"] for x in rows(pg))
    chk("this_week_from_monday", got == exp, "| %d vs %d (monday %s)" % (got, exp, monday))

    # ---- click goes to that bot's logs for the period ----
    pg.select_option("#rank-period", "30"); pg.wait_for_timeout(250)
    pg.click('#rank-list .rank-row[data-bot="Fox"]'); pg.wait_for_timeout(700)
    chk("click_opens_logs", pg.locator("#page-observations").is_visible() and pg.locator("#obs-content").is_visible())
    chk("click_filters", pg.input_value("#filter-robot") == "Fox" and pg.input_value("#filter-from") == D[29]
        and pg.input_value("#filter-to") == D[0], "| %s %s %s" % (pg.input_value("#filter-robot"),
        pg.input_value("#filter-from"), pg.input_value("#filter-to")))
    n = pg.eval_on_selector_all("#table-body tr[data-row]", "e => e.length")
    chk("click_shows_fox_logs", n == 6, "| %d rows (4 obs + 2 no data)" % n)

    # ---- a new log moves the ranking ----
    pg.click("#tab-dashboard"); pg.wait_for_timeout(300)
    pg.evaluate("""() => { entries.push({id:'new1', date: localToday(), robot:'Hugo', task:['sweep floor'],
                     issue:['none'], severity:0, notes:'', links:[], noData:false}); renderRobotFilter(); }""")
    pg.wait_for_timeout(200)
    hugo = next(x for x in rows(pg) if x["bot"] == "Hugo")
    chk("updates_on_new_log", hugo["val"] == 2, "| %s" % hugo)

    # ---- phone ----
    m = br.new_page(viewport={"width": 390, "height": 844}); H.watch_errors(m, errs)
    m.goto(url); H.seed(m, observations=obs); H.login(m); m.wait_for_timeout(1000)
    over = m.evaluate("() => document.documentElement.scrollWidth - innerWidth")
    chk("mobile_no_page_scroll", over <= 1, "| %dpx" % over)
    m.locator("#card-rank").screenshot(path="/tmp/rank_mobile.png")
    pg.locator("#card-rank").screenshot(path="/tmp/rank_desktop.png")

    chk("no_js_errors", not errs, "|%s" % errs[:3])
    br.close()

sys.exit(chk.report())
