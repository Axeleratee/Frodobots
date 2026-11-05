"""Logs page layout: Overview -> Late Upload Backlog -> folded Logged Observations."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_layout.html", config={"REST_DAYS": []})
D = {n: H.days_ago(n) for n in range(0, 60)}

# 130 ordinary entries (more than one page) plus three late uploads.
BOTS = ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]
obs = []
for i in range(130):
    obs.append(H.obs("N%03d" % i, D[1 + i % 50], BOTS[i % 5], by=H.CRIS if i % 2 else H.ADMIN))
obs.append(H.obs("L1", D[9], "Alpha",   by=H.CRIS,  late=True))
obs.append(H.obs("L2", D[7], "Charlie", by=H.CRIS,  late=True))
obs.append(H.obs("L3", D[5], "Echo",    by=H.ADMIN, late=True))
obs[-1]["entry"]["notes"] = "arrived after the weekend"
TOTAL = len(obs)

def body_rows(pg):
    return pg.eval_on_selector_all("#table-body tr[data-row]", "e => e.length")

with sync_playwright() as pw:
    br = pw.chromium.launch()
    pg = br.new_page(viewport={"width": 1440, "height": 1000})
    H.watch_errors(pg, errs); pg.on("dialog", lambda d: d.accept())
    pg.goto(url); H.seed(pg, observations=obs); H.login(pg)
    pg.click("#tab-logs"); pg.wait_for_timeout(1300)

    # ---- order ----
    order = pg.evaluate("() => [...document.querySelectorAll('#page-observations > .fb-card')].map(c => c.id)")
    chk("order", order == ["card-dates", "card-late-backlog", "card-obs", "card-audit"], "| %s" % order)

    # ---- observations: folded, count in the header ----
    chk("obs_starts_folded", pg.locator("#obs-content").is_hidden())
    chk("obs_aria_folded", pg.get_attribute("#obs-head", "aria-expanded") == "false")
    hc = pg.inner_text("#obs-head-count")
    chk("obs_header_total", hc.strip() == "%d observations" % TOTAL, "| %s" % hc)
    chk("folded_controls_not_focusable", pg.locator("#filter-search").is_hidden(),
        "| hidden controls must not be tabbable")

    # the backlog sits directly under the overview, not below the logs
    lb_top = pg.evaluate("() => document.getElementById('card-late-backlog').getBoundingClientRect().top")
    ob_top = pg.evaluate("() => document.getElementById('card-obs').getBoundingClientRect().top")
    chk("backlog_above_logs", lb_top < ob_top)

    # ---- open ----
    pg.click("#obs-head"); pg.wait_for_timeout(500)
    chk("obs_opens", pg.locator("#obs-content").is_visible())
    chk("obs_aria_open", pg.get_attribute("#obs-head", "aria-expanded") == "true")

    # ---- a page at a time ----
    chk("first_page_100", body_rows(pg) == 100, "| %d" % body_rows(pg))
    more = pg.inner_text("#obs-more")
    chk("more_says_how_many", "Showing 100 of %d" % TOTAL in more, "| %s" % more)
    pg.click('#obs-more button[data-more="page"]'); pg.wait_for_timeout(300)
    chk("show_more_loads_rest", body_rows(pg) == TOTAL, "| %d" % body_rows(pg))
    chk("all_shown_note", "Showing all %d" % TOTAL in pg.inner_text("#obs-more"))

    # a refresh keeps how far you had read; a filter change starts again
    pg.evaluate("() => render()")
    chk("refresh_keeps_page", body_rows(pg) == TOTAL)

    # ---- existing filters still work, and the header says it's filtered ----
    pg.select_option("#filter-robot", "Alpha"); pg.wait_for_timeout(300)
    n_alpha = sum(1 for o in obs if o["entry"]["robot"] == "Alpha")
    chk("filter_robot_works", body_rows(pg) == n_alpha, "| %d vs %d" % (body_rows(pg), n_alpha))
    chk("header_says_filtered", pg.inner_text("#obs-head-count").strip() == "%d of %d observations" % (n_alpha, TOTAL),
        "| %s" % pg.inner_text("#obs-head-count"))
    pg.fill("#filter-search", "zzz-no-such-thing"); pg.wait_for_timeout(300)
    chk("no_match_message", "Nothing matches" in pg.inner_text("#empty-state"))
    pg.click("#filter-clear"); pg.wait_for_timeout(300)
    chk("clear_restores_first_page", body_rows(pg) == 100, "| %d" % body_rows(pg))

    # ---- edit / delete actions are still on every row ----
    acts = pg.eval_on_selector_all("#table-body tr[data-row] button", "e => e.length")
    chk("row_actions_present", acts >= 200, "| %d buttons" % acts)

    # ---- fold again ----
    pg.click("#obs-head"); pg.wait_for_timeout(500)
    chk("obs_folds_again", pg.locator("#obs-content").is_hidden())

    # ---- backlog: compact cards, bot + reviewer filters ----
    chk("backlog_open", pg.locator("#lb-content").is_visible())
    cards = pg.inner_text("#lb-cards")
    chk("backlog_cards", all(k in cards for k in ("Total late uploads", "Unresolved", "Resolved")))
    bots = pg.eval_on_selector_all("#lb-robot option", "e => e.map(o => o.value)")
    chk("bot_choices_from_backlog", bots == ["", "Alpha", "Charlie", "Echo"], "| %s" % bots)
    pg.select_option("#lb-robot", "Charlie"); pg.wait_for_timeout(300)
    ids = pg.evaluate("() => [...document.querySelectorAll('#lb-body tr')].map(t => t.dataset.obs)")
    chk("filter_by_bot", ids == ["L2"], "| %s" % ids)
    pg.select_option("#lb-robot", ""); pg.select_option("#lb-reviewer", "boss"); pg.wait_for_timeout(300)
    ids = pg.evaluate("() => [...document.querySelectorAll('#lb-body tr')].map(t => t.dataset.obs)")
    chk("filter_by_reviewer", ids == ["L3"], "| %s" % ids)
    pg.click("#lb-clear"); pg.wait_for_timeout(300)
    pg.fill("#lb-search", "weekend"); pg.wait_for_timeout(300)
    ids = pg.evaluate("() => [...document.querySelectorAll('#lb-body tr')].map(t => t.dataset.obs)")
    chk("search_reaches_notes", ids == ["L3"], "| %s" % ids)
    pg.click("#lb-clear"); pg.wait_for_timeout(300)

    # ---- View goes to the original observation, opening the folded panel ----
    pg.locator('#lb-body tr[data-obs="L2"] .lb-open').click(); pg.wait_for_timeout(900)
    chk("view_opens_logs", pg.locator("#obs-content").is_visible())
    chk("view_shows_that_row", pg.locator('#table-body tr[data-row="L2"]').is_visible())
    chk("view_filters_to_it", pg.input_value("#filter-robot") == "Charlie" and pg.input_value("#filter-from") == D[7])
    in_view = pg.evaluate("""() => { const r = document.querySelector('#table-body tr[data-row="L2"]').getBoundingClientRect();
                                     return r.top >= 0 && r.bottom <= innerHeight; }""")
    chk("view_scrolls_to_row", in_view)

    # a row past the first page can still be reached
    pg.click("#filter-clear"); pg.wait_for_timeout(300)
    oldest = sorted(obs, key=lambda o: o["entry"]["date"])[0]["id"]
    pg.evaluate("id => flashRow(id)", oldest); pg.wait_for_timeout(500)
    chk("flash_reaches_past_page", pg.locator('#table-body tr[data-row="%s"]' % oldest).count() == 1)

    # ---- the overview's late count still opens the backlog ----
    pg.click("#lb-head"); pg.wait_for_timeout(400)
    pg.click("#dates-late-link"); pg.wait_for_timeout(600)
    chk("late_link_opens_backlog", pg.locator("#lb-content").is_visible())

    # ---- phone width: no sideways page scroll, header still usable ----
    m = br.new_page(viewport={"width": 390, "height": 844})
    H.watch_errors(m, errs)
    m.goto(url); H.seed(m, observations=obs); H.login(m)
    m.click("#tab-logs"); m.wait_for_timeout(1300)
    over = m.evaluate("() => document.documentElement.scrollWidth - innerWidth")
    chk("mobile_no_page_scroll", over <= 1, "| overflow %dpx" % over)
    m.click("#obs-head"); m.wait_for_timeout(500)
    chk("mobile_obs_opens", m.locator("#obs-content").is_visible())
    over = m.evaluate("() => document.documentElement.scrollWidth - innerWidth")
    chk("mobile_open_no_page_scroll", over <= 1, "| overflow %dpx" % over)

    pg.screenshot(path="/tmp/layout_desktop.png", full_page=True)
    m.screenshot(path="/tmp/layout_mobile.png", full_page=False)
    chk("no_js_errors", not errs, "|%s" % errs[:3])
    br.close()

sys.exit(chk.report())
