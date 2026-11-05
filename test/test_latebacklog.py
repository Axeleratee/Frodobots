"""Late Upload Backlog: collects itself, keeps its history, stays independent."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_lb.html", config={"REST_DAYS": []})
D = {n: H.days_ago(n) for n in range(0, 14)}

obs = [
    H.obs("L1", D[9], "Alpha",   by=H.CRIS,  late=True, logged_at=D[6] + "T09:00:00Z"),
    H.obs("L2", D[7], "Charlie", by=H.CRIS,  late=True, logged_at=D[5] + "T09:00:00Z"),
    H.obs("L3", D[5], "Echo",    by=H.ADMIN, late=True, logged_at=D[3] + "T09:00:00Z"),
    H.obs("N1", D[6], "Fox",     by=H.CRIS),                      # not late
    H.obs("N2", D[4], "Hugo",    by=H.ADMIN, no_data=True),       # not late
]
obs[0]["entry"]["notes"] = "footage arrived three days late"
# L1 was already resolved, then reopened: two events, newest wins.
events = [
    H.late_event("e1", "L1", "resolved",   D[4] + "T10:00:00Z"),
    H.late_event("e2", "L1", "unresolved", D[3] + "T11:00:00Z"),
    H.late_event("e3", "L2", "resolved",   D[2] + "T08:00:00Z"),
]

def rows(pg):
    return pg.evaluate("() => lateBacklogRows().map(r => [r.id, r.status])")

with sync_playwright() as pw:
    br = pw.chromium.launch()
    pg = br.new_page(viewport={"width": 1480, "height": 1200})
    H.watch_errors(pg, errs); pg.on("dialog", lambda d: d.accept())
    pg.goto(url); H.seed(pg, observations=obs, late_events=events); H.login(pg)
    pg.click("#tab-logs"); pg.wait_for_timeout(1200)

    # ---- it starts folded, so it costs a header instead of a screen ----
    chk("starts_folded", pg.locator("#lb-content").is_hidden())
    head = pg.inner_text("#lb-head")
    chk("header_shows_unresolved", "2 unresolved" in head, "| %s" % head.replace("\n", " "))
    pg.click("#lb-head"); pg.wait_for_timeout(500)
    chk("opens_on_click", pg.locator("#lb-content").is_visible())
    chk("aria_tracks_state", pg.get_attribute("#lb-head", "aria-expanded") == "true")

    # ---- it collects itself ----
    r = dict(rows(pg))
    chk("only_late_uploads", sorted(r) == ["L1", "L2", "L3"], "| %s" % sorted(r))
    chk("no_duplicates", len(rows(pg)) == 3)
    chk("default_is_unresolved", r["L3"] == "unresolved", "| never had an event")
    chk("newest_event_wins", r["L1"] == "unresolved",
        "| resolved then reopened: %s" % r["L1"])
    chk("resolved_shows_resolved", r["L2"] == "resolved")

    # ---- summary cards ----
    cards = pg.inner_text("#lb-cards")
    chk("card_total", "Total late uploads" in cards and "3" in cards, "| %s" % cards.replace("\n", " "))
    chk("card_unresolved", "Unresolved" in cards)
    chk("card_resolved", "Resolved" in cards)

    # ---- the table ----
    chk("table_rows", pg.eval_on_selector_all("#lb-body tr", "e => e.length") == 3)
    body = pg.inner_text("#lb-body")
    chk("shows_reviewer", "cris" in body and "boss" in body)
    chk("shows_notes", "footage arrived three days late" in body)
    chk("shows_history_count", "2 changes" in body, "| L1 has two events: %s" % body.replace("\n", " ")[:140])
    chk("names_who_resolved", "by boss" in body)

    # unresolved first by default, oldest of those at the top
    order = pg.evaluate("() => [...document.querySelectorAll('#lb-body tr')].map(t => t.dataset.obs)")
    chk("unresolved_first", order.index("L2") == 2, "| resolved L2 last: %s" % order)
    chk("oldest_unresolved_on_top", order[0] == "L1", "| %s" % order)

    # ---- the late-uploads count up in the overview opens it ----
    pg.click("#lb-head"); pg.wait_for_timeout(400)
    chk("folds_again", pg.locator("#lb-content").is_hidden())
    pg.click("#dates-late-link"); pg.wait_for_timeout(600)
    chk("overview_count_opens_it", pg.locator("#lb-content").is_visible(),
        "| the late count in the overview should open the backlog")

    # ---- resolve, and keep everything else intact ----
    before_late = pg.evaluate("() => entries.filter(isLateUpload).length")
    pg.locator('#lb-body tr[data-obs="L3"] .lb-toggle').click(); pg.wait_for_timeout(1200)
    chk("resolve_works", dict(rows(pg))["L3"] == "resolved")
    chk("late_flag_untouched",
        pg.evaluate("() => entries.filter(isLateUpload).length") == before_late,
        "| resolving must not clear the late flag")
    chk("still_in_the_list", len(rows(pg)) == 3, "| resolved items are not hidden")
    chk("history_is_appended", pg.evaluate("() => _lateEvents.length") == 4,
        "| an event was added, nothing was edited")

    # ---- reopen adds another event ----
    pg.locator('#lb-body tr[data-obs="L3"] .lb-toggle').click(); pg.wait_for_timeout(1200)
    chk("reopen_works", dict(rows(pg))["L3"] == "unresolved")
    chk("reopen_also_appends", pg.evaluate("() => _lateEvents.length") == 5)

    # ---- independent of the review status ----
    chk("review_status_untouched", pg.evaluate("""() => {
        const r = allExpected().find(x => x.robot === 'Echo');
        return r ? r.status : 'none'; }""") in ("done", "pending", "none"),
        "| resolving a backlog item says nothing about the review")

    # ---- filters, search, sort ----
    pg.select_option("#lb-status", "resolved"); pg.wait_for_timeout(600)
    chk("filter_status", pg.evaluate("""() => [...document.querySelectorAll('#lb-body tr')]
        .every(t => t.innerText.includes('Resolved'))"""))
    pg.select_option("#lb-status", ""); pg.wait_for_timeout(400)
    pg.fill("#lb-search", "charlie"); pg.wait_for_timeout(600)
    chk("search", pg.eval_on_selector_all("#lb-body tr", "e => e.length") == 1)
    pg.fill("#lb-search", ""); pg.wait_for_timeout(400)
    pg.fill("#lb-from", D[6]); pg.wait_for_timeout(600)
    chk("filter_date", pg.eval_on_selector_all("#lb-body tr", "e => e.length") == 1,
        "| only L3 is on or after that date")
    pg.click("#lb-clear"); pg.wait_for_timeout(600)
    chk("clear_restores", pg.eval_on_selector_all("#lb-body tr", "e => e.length") == 3)

    pg.select_option("#lb-sort", "oldest"); pg.wait_for_timeout(600)
    o2 = pg.evaluate("() => [...document.querySelectorAll('#lb-body tr')].map(t => t.dataset.date)")
    chk("sort_oldest", o2 == sorted(o2), "| %s" % o2)
    pg.select_option("#lb-sort", "newest"); pg.wait_for_timeout(600)
    o3 = pg.evaluate("() => [...document.querySelectorAll('#lb-body tr')].map(t => t.dataset.date)")
    chk("sort_newest", o3 == sorted(o3, reverse=True), "| %s" % o3)

    # ---- open the original observation ----
    pg.select_option("#lb-sort", "unresolved"); pg.wait_for_timeout(500)
    tr = pg.locator("#lb-body tr").first
    d0, b0 = tr.get_attribute("data-date"), tr.get_attribute("data-bot")
    tr.locator(".lb-open").click(); pg.wait_for_timeout(900)
    chk("open_filters_the_logs",
        pg.input_value("#filter-from") == d0 and pg.input_value("#filter-robot") == b0,
        "| %s %s" % (b0, d0))

    pg.locator("#card-late-backlog").screenshot(path="/tmp/latebacklog.png")

    # ---- a new late observation joins by itself ----
    pg.click("#tab-dashboard"); pg.wait_for_timeout(600)
    pg.fill("#f-date", D[3]); pg.select_option("#f-robot", "Igor"); pg.wait_for_timeout(300)
    pg.check("#f-late")
    pg.click("#f-task"); pg.wait_for_timeout(200)
    pg.click("#f-task .ms-opt:has-text('sweep floor')")
    pg.click("#card-log >> text=Log an observation"); pg.wait_for_timeout(250)
    pg.click("#btn-save"); pg.wait_for_timeout(1400)
    chk("new_late_appears", len(rows(pg)) == 4, "| %d" % len(rows(pg)))
    chk("new_one_is_unresolved",
        [s for i, s in rows(pg) if i not in ("L1", "L2", "L3")] == ["unresolved"])

    # ---- viewers may look, not act ----
    p2 = br.new_page(viewport={"width": 1480, "height": 1000})
    H.watch_errors(p2, errs)
    p2.goto(url); H.seed(p2, observations=obs, late_events=events); H.login(p2, "ana")
    p2.click("#tab-logs"); p2.wait_for_timeout(1100)
    p2.click("#lb-head"); p2.wait_for_timeout(500)
    chk("viewer_sees_backlog", p2.eval_on_selector_all("#lb-body tr", "e => e.length") == 3)
    chk("viewer_cannot_resolve", p2.eval_on_selector_all("#lb-body .lb-toggle", "e => e.length") == 0)
    chk("viewer_can_still_open", p2.eval_on_selector_all("#lb-body .lb-open", "e => e.length") == 3)
    p2.close()

    # ---- SQL not run ----
    p3 = br.new_page(viewport={"width": 1480, "height": 900})
    H.watch_errors(p3, errs)
    p3.goto(url); H.seed(p3, observations=obs, missing=["late_backlog_events"]); H.login(p3)
    p3.click("#tab-logs"); p3.wait_for_timeout(1100)
    p3.click("#lb-head"); p3.wait_for_timeout(500)
    chk("missing_table_explained", "supabase-late-backlog.sql" in p3.inner_text("#lb-setup"))
    chk("missing_table_list_still_works",
        p3.eval_on_selector_all("#lb-body tr", "e => e.length") == 3,
        "| the list comes from the observations, not from that table")
    chk("missing_table_hides_resolve",
        p3.eval_on_selector_all("#lb-body .lb-toggle", "e => e.length") == 0)
    chk("missing_table_app_alive", p3.evaluate("() => entries.length") == 5)

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
