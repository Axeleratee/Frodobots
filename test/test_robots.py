"""Robots managed from Settings: add, retire, restore, delete-if-unused."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build("app_robots.html", config={"REST_DAYS": []})
D = {n: H.days_ago(n) for n in range(0, 30)}
NINE = ["Alpha", "Charlie", "Echo", "Fox", "Godzilla", "Hugo", "Igor", "Jackie", "Kilo"]

def robot_opt(i, name, retired=None):
    return {"id": "r-" + name, "kind": "robot", "key": name, "label": name,
            "severity": None, "sort_order": (i + 1) * 10, "retired_at": retired}
TASKS = [{"id": "t1", "kind": "task", "key": "sweep floor", "label": "sweep floor", "sort_order": 10},
         {"id": "t2", "kind": "task", "key": "fold towels", "label": "fold towels", "sort_order": 20}]

obs = [H.obs("O1", D[3], "Alpha"), H.obs("O2", D[12], "Kilo", by=H.CRIS), H.obs("O3", D[4], "Charlie")]

def values(pg, sel):
    return pg.eval_on_selector_all(sel + " option", "e => e.map(o => o.value)")

with sync_playwright() as pw:
    br = pw.chromium.launch()

    # ---------- before supabase-robots.sql: nothing changes ----------
    p0 = br.new_page(viewport={"width": 1400, "height": 1000})
    H.watch_errors(p0, errs); p0.on("dialog", lambda d: d.accept())
    p0.goto(url); H.seed(p0, observations=obs, options=TASKS); H.login(p0); p0.wait_for_timeout(900)
    chk("fallback_nine", values(p0, "#f-robot") == NINE + ["__other"], "| %s" % values(p0, "#f-robot"))
    chk("tasks_still_load", p0.evaluate("() => _taskOptions.map(o => o.key)") == ["sweep floor", "fold towels"],
        "| select('*') must not break the options load")
    p0.click("#tab-settings"); p0.wait_for_timeout(500)
    chk("warning_before_sql", "supabase-robots.sql" in p0.inner_text("#robots-warning"))
    chk("add_disabled_before_sql", p0.is_disabled("#btn-robot-add"))
    chk("lists_nine_before_sql", p0.eval_on_selector_all("#robot-list [data-robot]", "e => e.length") == 9)
    p0.close()

    # ---------- after: managed list, Kilo retired ----------
    dialogs = []
    def on_dialog(d):
        dialogs.append(d.message); d.accept()
    pg = br.new_page(viewport={"width": 1400, "height": 1000})
    H.watch_errors(pg, errs); pg.on("dialog", on_dialog)
    robots = [robot_opt(i, n, retired=(D[2] + "T08:00:00Z" if n == "Kilo" else None)) for i, n in enumerate(NINE)]
    pg.goto(url)
    H.seed(pg, observations=obs, options=TASKS + robots,
           assignments=[H.assign("A1", H.ANA, "Charlie", D[20])])
    H.login(pg); pg.wait_for_timeout(1000)

    active = [n for n in NINE if n != "Kilo"]
    chk("retired_not_in_log_form", values(pg, "#f-robot") == active + ["__other"], "| %s" % values(pg, "#f-robot"))
    pg.click("#tab-users"); pg.wait_for_timeout(500)
    chk("retired_not_assignable", "Kilo" not in values(pg, "#assign-robot") and "Alpha" in values(pg, "#assign-robot"))
    chk("retired_kept_in_filter", "Kilo" in values(pg, "#filter-robot"),
        "| its history must stay filterable: %s" % values(pg, "#filter-robot"))
    chk("retired_labelled_in_filter",
        pg.evaluate("() => [...document.querySelectorAll('#filter-robot option')].some(o => o.textContent === 'Kilo (retired)')"))

    pg.click("#tab-settings"); pg.wait_for_timeout(500)
    chk("no_warning_after_sql", pg.locator("#robots-warning").is_hidden())
    chk("card_visible_to_admin", pg.locator("#card-robots").is_visible())
    names = pg.eval_on_selector_all("#robot-list [data-robot]", "e => e.map(x => x.dataset.robot)")
    chk("retired_listed_last", names[-1] == "Kilo", "| %s" % names)
    alpha = pg.inner_text('#robot-list [data-robot="Alpha"]')
    chk("usage_shown", "1 log" in alpha, "| %s" % alpha)
    chk("no_delete_with_history", pg.locator('#robot-list [data-robot="Alpha"] [data-act="delete"]').count() == 0)
    chk("no_delete_with_assignment", pg.locator('#robot-list [data-robot="Charlie"] [data-act="delete"]').count() == 0)

    # ---- add ----
    pg.fill("#robot-new", "  Lima "); pg.click("#btn-robot-add"); pg.wait_for_timeout(700)
    chk("added_to_list", pg.locator('#robot-list [data-robot="Lima"]').count() == 1)
    chk("added_to_log_form", values(pg, "#f-robot")[-2:] == ["Lima", "__other"], "| %s" % values(pg, "#f-robot"))
    chk("added_assignable", "Lima" in values(pg, "#assign-robot"))
    chk("stored_as_robot", pg.evaluate(
        "() => JSON.parse(localStorage.getItem('__mock_options')).some(o => o.kind === 'robot' && o.key === 'Lima' && !o.retired_at)"))
    pg.fill("#robot-new", "lima"); pg.click("#btn-robot-add"); pg.wait_for_timeout(500)
    chk("duplicate_refused", "already on the list" in pg.inner_text("#robot-status"), "| %s" % pg.inner_text("#robot-status"))
    pg.fill("#robot-new", "kilo"); pg.click("#btn-robot-add"); pg.wait_for_timeout(500)
    chk("retired_duplicate_points_to_restore", "Restore" in pg.inner_text("#robot-status"))
    chk("lima_deletable_while_unused", pg.locator('#robot-list [data-robot="Lima"] [data-act="delete"]').count() == 1)

    # ---- delete (unused only) ----
    pg.click('#robot-list [data-robot="Lima"] [data-act="delete"]'); pg.wait_for_timeout(700)
    chk("deleted", pg.locator('#robot-list [data-robot="Lima"]').count() == 0 and "Lima" not in values(pg, "#f-robot"))

    # ---- retire, with an open assignment ----
    n_obs = pg.evaluate("() => entries.length")
    dialogs.clear()
    pg.click('#robot-list [data-robot="Charlie"] [data-act="retire"]'); pg.wait_for_timeout(700)
    chk("retire_warns_open_assignment", dialogs and "open assignment" in dialogs[0] and "ana" in dialogs[0],
        "| %s" % (dialogs[:1]))
    chk("retired_leaves_log_form", "Charlie" not in values(pg, "#f-robot"))
    chk("retire_keeps_logs", pg.evaluate("() => entries.length") == n_obs and
        pg.evaluate("() => entries.some(e => e.robot === 'Charlie')"))
    chk("retire_keeps_assignment", pg.evaluate("() => _assignments.some(a => a.robot === 'Charlie' && !a.ends_on)"),
        "| retiring must not rewrite assignment history")
    chk("retire_shows_badge", "Retired" in pg.inner_text('#robot-list [data-robot="Charlie"]'))

    # ---- restore ----
    pg.click('#robot-list [data-robot="Kilo"] [data-act="restore"]'); pg.wait_for_timeout(700)
    chk("restored_to_log_form", "Kilo" in values(pg, "#f-robot"))

    # ---- editing an old log on a retired robot keeps the robot ----
    pg.evaluate("() => startEdit('O3')"); pg.wait_for_timeout(500)
    chk("edit_retired_keeps_robot", pg.input_value("#f-robot") == "Charlie", "| %s" % pg.input_value("#f-robot"))
    chk("edit_retired_not_other", pg.locator("#f-robot-other").is_hidden())
    pg.close()

    # ---------- non-admins never see the card ----------
    for who in ("cris", "ana"):
        pv = br.new_page(viewport={"width": 1200, "height": 900})
        H.watch_errors(pv, errs)
        pv.goto(url); H.seed(pv, observations=obs, options=TASKS + robots); H.login(pv, who); pv.wait_for_timeout(700)
        chk("hidden_from_" + who, pv.locator("#card-robots").is_hidden())
        pv.close()

    chk("no_js_errors", not errs, "|%s" % errs[:3])
    br.close()

sys.exit(chk.report())
