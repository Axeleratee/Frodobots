"""User Performance: 7D / 30D / 90D / All time on the overview and on each profile."""
import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_perfperiod.html", config={"REST_DAYS": []})
D = {n: H.days_ago(n) for n in range(0, 120)}

obs = []
for n in (0, 2, 5):                        # inside 7 days
    obs.append(H.obs("w%d" % n, D[n], "Alpha", by=H.CRIS))
for n in range(10, 20):                    # inside 30 days
    obs.append(H.obs("m%d" % n, D[n], "Echo", by=H.CRIS))
for n in (50, 60, 70, 80, 85):             # inside 90 days only
    obs.append(H.obs("q%d" % n, D[n], "Fox", by=H.CRIS))
AUDIT = [{"id": "a1", "created_at": D[0] + "T03:05:00Z", "actor": "cris",
          "action": "created", "robot": "Kilo", "obs_date": D[2]}]

def logs_for(pg, user):
    return pg.evaluate("""u => { const tr = document.querySelector('.perf-row[data-user="' + u + '"]');
                                 return tr ? +tr.children[2].textContent : null; }""", user)
def active_chip(pg, scope):
    return pg.evaluate("s => (document.querySelector(s + ' .perf-win.dv-tab-on') || {}).textContent || ''", scope)
def stat(pg, label):
    return pg.evaluate("""l => { const d = [...document.querySelectorAll('#perf-detail .fb-card > div:nth-of-type(2) > div')]
                                 .find(x => x.innerText.includes(l)); return d ? parseInt(d.innerText, 10) : null; }""", label)
def bars(pg):
    return pg.eval_on_selector_all("#perf-detail svg rect", "e => e.length")

with sync_playwright() as pw:
    br = pw.chromium.launch()
    ctx = br.new_context(viewport={"width": 1400, "height": 1100}, timezone_id="Asia/Manila")
    pg = ctx.new_page(); H.watch_errors(pg, errs)
    pg.goto(url); H.seed(pg, observations=obs)
    pg.evaluate("a => localStorage.setItem('__mock_audit', JSON.stringify(a))", AUDIT)
    pg.reload(); H.login(pg)
    pg.click("#tab-performance"); pg.wait_for_timeout(1300)

    # ---- overview ----
    chk("overview_has_buttons", pg.locator(".perf-period .perf-win").count() == 5)
    chk("default_30d", active_chip(pg, ".perf-period") == "30D")
    chk("label_says_period", "Last 30 days" in pg.inner_text("#perf-period-label"))
    chk("30d_count", logs_for(pg, "cris") == 13, "| %s" % logs_for(pg, "cris"))
    pg.click('.perf-period .perf-win[data-win="7"]'); pg.wait_for_timeout(300)
    chk("7d_count", logs_for(pg, "cris") == 3, "| %s" % logs_for(pg, "cris"))
    chk("7d_active", active_chip(pg, ".perf-period") == "7D")
    pg.click('.perf-period .perf-win[data-win="90"]'); pg.wait_for_timeout(300)
    chk("90d_count", logs_for(pg, "cris") == 18)
    pg.click('.perf-period .perf-win[data-win="0"]'); pg.wait_for_timeout(300)
    chk("all_count", logs_for(pg, "cris") == 18)
    chk("all_label", "All time" in pg.inner_text("#perf-period-label"))

    # ---- profile ----
    pg.click('.perf-row[data-user="cris"]'); pg.wait_for_timeout(500)
    chk("profile_open", pg.locator("#perf-detail").is_visible())
    chk("profile_has_buttons", pg.locator("#perf-detail .perf-win").count() == 5)
    chk("profile_shows_current", active_chip(pg, "#perf-detail") == "All time")

    pg.click('#perf-detail .perf-win[data-win="30"]'); pg.wait_for_timeout(400)
    chk("stays_in_profile", pg.locator("#perf-detail").is_visible() and pg.locator("#perf-overview").is_hidden())
    chk("profile_30d_obs", stat(pg, "Observations logged") == 13, "| %s" % stat(pg, "Observations logged"))
    chk("profile_30d_daily_bars", bars(pg) == 30, "| %d" % bars(pg))
    chk("profile_30d_title", "per day, last 30 days" in pg.inner_text("#perf-detail"))
    chk("profile_label", "Last 30 days" in pg.inner_text("#perf-detail"))

    pg.click('#perf-detail .perf-win[data-win="7"]'); pg.wait_for_timeout(400)
    chk("profile_7d_obs", stat(pg, "Observations logged") == 3)
    chk("profile_7d_bars", bars(pg) == 7, "| %d" % bars(pg))
    chk("profile_7d_bots", "Alpha" in pg.inner_text("#perf-detail") and "Echo 10" not in pg.inner_text("#perf-detail"))

    pg.click('#perf-detail .perf-win[data-win="90"]'); pg.wait_for_timeout(400)
    chk("profile_90d_weekly", bars(pg) == 13 and "per week" in pg.inner_text("#perf-detail"), "| %d" % bars(pg))

    # Recent activity in local time: 03:05 UTC is 11:05 in Manila.
    chk("activity_local_time", (D[0] + " 11:05") in pg.inner_text("#perf-detail"),
        "| %s" % pg.inner_text("#perf-detail")[-200:])

    # ---- custom range, inside the profile ----
    def set_range(scope, f, t):
        pg.evaluate("""([s, f, t]) => { const box = document.querySelector(s + ' .perf-from').closest('span');
            box.querySelector('.perf-from').value = f; box.querySelector('.perf-to').value = t;
            box.querySelector('.perf-to').dispatchEvent(new Event('change', { bubbles: true })); }""", [scope, f, t])
        pg.wait_for_timeout(400)
    pg.click('#perf-detail .perf-win[data-win="custom"]'); pg.wait_for_timeout(400)
    chk("custom_shows_dates", pg.locator("#perf-detail .perf-from").count() == 1)
    chk("custom_defaults_30d", pg.input_value("#perf-detail .perf-from") == D[29] and pg.input_value("#perf-detail .perf-to") == D[0])
    chk("custom_default_count", stat(pg, "Observations logged") == 13)
    set_range("#perf-detail", D[19], D[10])
    chk("custom_range_count", stat(pg, "Observations logged") == 10, "| %s" % stat(pg, "Observations logged"))
    chk("custom_end_respected", "Alpha" not in pg.inner_text("#perf-detail").split("Bots covered")[1].split("Recent")[0],
        "| logs after the end date must not count")
    chk("custom_daily_bars", bars(pg) == 10, "| %d" % bars(pg))
    chk("custom_label", "10 days" in pg.inner_text("#perf-detail"))
    chk("still_in_profile", pg.locator("#perf-detail").is_visible())
    set_range("#perf-detail", D[10], D[80])            # reversed on purpose
    chk("reversed_dates_swapped", pg.input_value("#perf-detail .perf-from") == D[80] and
        pg.input_value("#perf-detail .perf-to") == D[10])
    chk("custom_long_count", stat(pg, "Observations logged") == 14, "| %s" % stat(pg, "Observations logged"))
    chk("custom_long_weekly", bars(pg) == 11 and "per week" in pg.inner_text("#perf-detail"), "| %d" % bars(pg))

    # ---- back keeps the chosen period ----
    pg.click("#perf-back"); pg.wait_for_timeout(300)
    chk("back_keeps_period", active_chip(pg, ".perf-period") == "Custom" and logs_for(pg, "cris") == 14,
        "| %s %s" % (active_chip(pg, ".perf-period"), logs_for(pg, "cris")))
    chk("overview_shows_custom_dates", pg.input_value(".perf-period .perf-from") == D[80])
    pg.click('.perf-period .perf-win[data-win="30"]'); pg.wait_for_timeout(300)
    chk("back_to_preset", logs_for(pg, "cris") == 13 and pg.locator(".perf-period .perf-from").count() == 0)

    # ---- phone ----
    m = br.new_context(viewport={"width": 390, "height": 844}, timezone_id="Asia/Manila").new_page()
    H.watch_errors(m, errs)
    m.goto(url); H.seed(m, observations=obs); H.login(m)
    m.click("#tab-performance"); m.wait_for_timeout(1000)
    m.click('.perf-row[data-user="cris"]'); m.wait_for_timeout(500)
    over = m.evaluate("() => document.documentElement.scrollWidth - innerWidth")
    chk("mobile_profile_fits", over <= 1, "| %dpx" % over)
    m.locator("#perf-detail").screenshot(path="/tmp/perf_mobile.png")
    pg.click('.perf-row[data-user="cris"]'); pg.wait_for_timeout(400)
    pg.click('#perf-detail .perf-win[data-win="30"]'); pg.wait_for_timeout(400)
    pg.locator("#perf-detail").screenshot(path="/tmp/perf_desktop.png")

    chk("no_js_errors", not errs, "|%s" % errs[:3])
    br.close()

sys.exit(chk.report())
