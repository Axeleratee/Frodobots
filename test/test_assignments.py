"""The assignments admin UI: create, end, delete, and refuse double-cover."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build()
T = H.days_ago(0)

with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(viewport={"width": 1400, "height": 1100})
    H.watch_errors(pg, errs)
    dialogs = []
    mode = {"accept": True}
    pg.on("dialog", lambda d: (dialogs.append(d.message),
                               d.accept() if mode["accept"] else d.dismiss()))
    pg.goto(url)
    H.seed(pg, observations=[H.obs("o1", H.days_ago(1), "Alpha")],
           assignments=[H.assign("a1", H.CRIS, "Echo", H.days_ago(10))])
    H.login(pg)
    pg.click("#tab-users"); pg.wait_for_timeout(900)

    chk("card_visible", pg.is_visible("#card-assign"))
    chk("existing_rendered", "Echo" in pg.inner_text("#assign-list"))
    chk("grouped_by_person", "cris" in pg.inner_text("#assign-list"))

    opts = pg.eval_on_selector_all("#assign-user option", "e => e.map(o => o.textContent.trim())")
    chk("viewer_not_assignable", "ana" not in opts and "cris" in opts, "| %s" % opts)
    chk("start_defaults_today", pg.input_value("#assign-start") == T)

    # assign
    pg.select_option("#assign-user", label="cris")
    pg.select_option("#assign-robot", "Alpha")
    pg.click("#assign-add"); pg.wait_for_timeout(900)
    chk("assigned", pg.evaluate("() => _assignments.length") == 2,
        "| %d" % pg.evaluate("() => _assignments.length"))
    chk("assign_toast", pg.eval_on_selector_all(".fb-toast.fb-toast-on", "e => e.length") == 1)

    # duplicate cover refused
    pg.click("#assign-add"); pg.wait_for_timeout(700)
    chk("double_cover_refused", pg.evaluate("() => _assignments.length") == 2,
        "| %s" % pg.inner_text("#assign-status"))
    chk("double_cover_explains", "already covers" in pg.inner_text("#assign-status"))

    # a second person on the same robot IS allowed (shared / stand-in)
    pg.evaluate("""() => {
      const p = JSON.parse(localStorage.getItem('__mock_profiles'));
      p['uid-ana@robotqa.local'].role = 'editor';
      localStorage.setItem('__mock_profiles', JSON.stringify(p));
    }""")
    pg.evaluate("() => loadTeam()"); pg.wait_for_timeout(500)
    pg.select_option("#assign-user", label="ana")
    pg.select_option("#assign-robot", "Alpha")
    pg.click("#assign-add"); pg.wait_for_timeout(900)
    chk("overlap_between_people_allowed", pg.evaluate("() => _assignments.length") == 3,
        "| %d" % pg.evaluate("() => _assignments.length"))

    # end today -> keeps the row, sets ends_on
    before = pg.evaluate("() => _assignments.length")
    pg.locator("#assign-list .asg-end").first.click(); pg.wait_for_timeout(900)
    chk("end_keeps_row", pg.evaluate("() => _assignments.length") == before)
    chk("end_sets_date",
        pg.evaluate("() => _assignments.filter(a => a.ends_on).length") == 1)

    # "End today" = responsible THROUGH today, so it is still active now and
    # the row says when it closes rather than offering the button again.
    txt = pg.inner_text("#assign-list")
    chk("end_shows_closing_date", ("ends " + T) in txt, "| %s" % txt.replace("\n", " ")[:90])
    chk("end_button_spent",
        pg.eval_on_selector_all("#assign-list .asg-end", "e => e.length") == 2,
        "| 3 rows, 1 ending -> 2 End buttons left")

    # a row that ended in the past is hidden until asked for
    pg.evaluate("""([past]) => {
      const a = JSON.parse(localStorage.getItem('__mock_assignments'));
      a[0].ends_on = past;
      localStorage.setItem('__mock_assignments', JSON.stringify(a));
    }""", [H.days_ago(3)])
    pg.evaluate("() => loadAssignments()"); pg.wait_for_timeout(600)
    chk("past_ended_hidden", "ended" not in pg.inner_text("#assign-list"))
    pg.check("#assign-show-ended"); pg.wait_for_timeout(500)
    chk("past_ended_shown_when_asked", "ended" in pg.inner_text("#assign-list"))

    # delete asks first and warns that End keeps history
    dialogs.clear()
    pg.locator("#assign-list .asg-del").first.click(); pg.wait_for_timeout(900)
    chk("delete_confirms", len(dialogs) == 1 and "End today" in dialogs[0],
        "| %s" % (dialogs[0][:60] if dialogs else "none"))
    chk("deleted", pg.evaluate("() => _assignments.length") == before - 1)

    # SQL-not-run case must explain itself, not break
    pg2 = br.new_page(viewport={"width": 1400, "height": 1000})
    H.watch_errors(pg2, errs)
    pg2.goto(url)
    H.seed(pg2, observations=[H.obs("o1", H.days_ago(1), "Alpha")], missing=["assignments"])
    H.login(pg2)
    pg2.click("#tab-users"); pg2.wait_for_timeout(900)
    chk("missing_table_explained", "supabase-team.sql" in pg2.inner_text("#assign-list"))
    chk("missing_table_app_alive", pg2.evaluate("() => entries.length") == 1)

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
