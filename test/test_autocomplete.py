"""Saving a log finishes the bot-day, with an opt-out and a way back."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
D = {n: H.days_ago(n) for n in range(0, 12)}
asg = [H.assign("a1", H.ADMIN, "Alpha", D[9]), H.assign("a2", H.ADMIN, "Echo", D[9])]

auto = H.build("app_auto.html")                                   # default: on
manual = H.build("app_manual.html", config={"AUTO_COMPLETE_ON_LOG": False})

def log(pg, date, bot, tick=False, nodata=False, task="sweep floor"):
    pg.fill("#f-date", date); pg.select_option("#f-robot", bot); pg.wait_for_timeout(300)
    if nodata:
        pg.check("#f-nodata"); pg.wait_for_timeout(200)
    else:
        pg.click("#f-task"); pg.wait_for_timeout(200)
        pg.click("#f-task .ms-opt:has-text('%s')" % task)
        pg.click("#card-log >> text=Log an observation"); pg.wait_for_timeout(250)
    if tick: pg.check("#f-done")
    pg.click("#btn-save"); pg.wait_for_timeout(1300)

def status_of(pg, date, bot):
    return pg.evaluate("""([d,b]) => {
        const t = _tasks.find(x => x.obs_date === d && x.robot === b);
        return t ? t.status : null; }""", [date, bot])

with sync_playwright() as pw:
    br = pw.chromium.launch()

    # ---------- default: logging finishes it ----------
    pg = br.new_page(viewport={"width": 1440, "height": 1100})
    H.watch_errors(pg, errs); pg.on("dialog", lambda d: d.accept())
    pg.goto(auto); H.seed(pg, observations=[], assignments=asg, tasks=[]); H.login(pg)

    chk("setting_on_by_default", pg.evaluate("() => AUTO_COMPLETE_ON_LOG") is True)
    chk("label_is_inverted", "not finished" in pg.inner_text("#f-done-label"),
        "| %s" % pg.inner_text("#f-done-label"))

    log(pg, D[5], "Alpha")
    chk("plain_save_completes", status_of(pg, D[5], "Alpha") == "completed",
        "| %s" % status_of(pg, D[5], "Alpha"))
    chk("toast_says_done", "marked done" in pg.inner_text(".fb-toast"))

    # ---------- the opt-out keeps it open ----------
    log(pg, D[4], "Alpha", tick=True)
    chk("tick_keeps_it_open", status_of(pg, D[4], "Alpha") is None,
        "| still working on it: %s" % status_of(pg, D[4], "Alpha"))
    chk("toast_says_open", "left open" in pg.inner_text(".fb-toast"),
        "| %s" % pg.inner_text(".fb-toast"))
    chk("tick_resets_after_save", pg.eval_on_selector("#f-done", "e => !e.checked"))

    # a second log on that same day, this time finishing it
    log(pg, D[4], "Alpha", task="clean up the room")
    chk("second_log_can_finish", status_of(pg, D[4], "Alpha") == "completed")
    chk("both_observations_kept",
        pg.evaluate("([d]) => entries.filter(e => e.date === d && e.robot === 'Alpha').length", [D[4]]) == 2)

    # ---------- no data still finishes regardless ----------
    log(pg, D[3], "Echo", tick=True, nodata=True)
    chk("nodata_finishes_even_when_ticked", status_of(pg, D[3], "Echo") == "completed",
        "| nothing to come back to")

    # ---------- it is reversible ----------
    pg.click("#tab-tracker"); pg.wait_for_timeout(900)
    pg.evaluate("""([d,b]) => {
        const t = _tasks.find(x => x.obs_date === d && x.robot === b);
        return setTaskStatus(t.id, 'pending'); }""", [D[5], "Alpha"])
    pg.wait_for_timeout(1200)
    chk("can_be_reopened", status_of(pg, D[5], "Alpha") == "pending")

    # editing an old entry must not silently re-close it
    pg.click("#tab-logs"); pg.wait_for_timeout(500)
    open_one = [D[5], "Alpha"]
    if open_one:
        pg.click("#tab-dashboard"); pg.wait_for_timeout(500)
        rowid = pg.evaluate("""([d,b]) => { const e = entries.find(x => x.date === d && x.robot === b);
                                            return e ? e.id : null; }""", open_one)
        if rowid:
            pg.evaluate("([id]) => startEdit(id)", [rowid]); pg.wait_for_timeout(600)
            chk("edit_defaults_to_leaving_it_alone",
                pg.eval_on_selector("#f-done", "e => e.checked"),
                "| the opt-out starts ticked when editing")
            pg.click("#btn-save"); pg.wait_for_timeout(1300)
            chk("edit_did_not_reclose", status_of(pg, open_one[0], open_one[1]) == "pending",
                "| %s" % status_of(pg, open_one[0], open_one[1]))
    pg.close()

    # ---------- the old behaviour is still available ----------
    pg2 = br.new_page(viewport={"width": 1440, "height": 1100})
    H.watch_errors(pg2, errs); pg2.on("dialog", lambda d: d.accept())
    pg2.goto(manual); H.seed(pg2, observations=[], assignments=asg, tasks=[]); H.login(pg2)
    chk("setting_can_be_off", pg2.evaluate("() => AUTO_COMPLETE_ON_LOG") is False)
    chk("label_is_normal", "I am finished" in pg2.inner_text("#f-done-label"),
        "| %s" % pg2.inner_text("#f-done-label"))
    log(pg2, D[5], "Alpha")
    chk("manual_plain_save_completes_nothing", status_of(pg2, D[5], "Alpha") is None)
    log(pg2, D[6], "Alpha", tick=True)
    chk("manual_tick_completes", status_of(pg2, D[6], "Alpha") == "completed")
    log(pg2, D[7], "Echo", nodata=True)
    chk("manual_nodata_still_completes", status_of(pg2, D[7], "Echo") == "completed")
    pg2.close()

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
