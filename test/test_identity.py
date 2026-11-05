"""Attribution must follow the user id, not a stored name."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from playwright.sync_api import sync_playwright
import harness as H

chk = H.Checks(); errs = []
url = H.build()

# "cris" wrote o2, but the row still carries the OLD name he was logged under.
rows = [
    H.obs("o1", H.days_ago(1), "Alpha", by=H.ADMIN),
    H.obs("o2", H.days_ago(1), "Charlie", by=H.CRIS),
    H.obs("o3", H.days_ago(2), "Echo", by=H.CRIS),
]
rows[1]["entry"]["loggedBy"] = "oldname"
rows[2]["entry"]["loggedBy"] = "oldname"
# A legacy row from before created_by existed: name only, no id.
legacy = H.obs("o4", H.days_ago(4), "Fox", by=H.CRIS)
legacy["created_by"] = None
legacy["entry"]["loggedBy"] = "someone_who_left"
rows.append(legacy)

with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(viewport={"width": 1400, "height": 1000})
    H.watch_errors(pg, errs)
    pg.goto(url); H.seed(pg, observations=rows); H.login(pg)

    chk("roster_loaded", pg.evaluate("() => _team.length") == 3,
        "| %d" % pg.evaluate("() => _team.length"))
    chk("created_by_carried", pg.evaluate("() => entries.filter(e => e._by).length") == 3)
    chk("created_at_carried", pg.evaluate("() => entries.filter(e => e._at).length") == 4,
        "| needed for turnaround")

    names = pg.evaluate("() => entries.map(observerName)")
    chk("renamed_user_resolves", names.count("cris") == 2,
        "| stored 'oldname', roster says 'cris' -> %s" % names)
    chk("legacy_row_falls_back", "someone_who_left" in names,
        "| row with no user id keeps its stored name")

    pg.click("#tab-logs"); pg.wait_for_timeout(700)
    pg.click("#obs-head"); pg.wait_for_timeout(400)   # Logged Observations starts folded
    opts = pg.eval_on_selector_all("#filter-user option", "els => els.map(e => e.value)")
    chk("filter_uses_current_name", "cris" in opts and "oldname" not in opts, "| %s" % opts)

    pg.select_option("#filter-user", "cris"); pg.wait_for_timeout(500)
    chk("filtering_by_new_name_works",
        pg.eval_on_selector_all("#table-body tr[data-row]", "e => e.length") == 2)

    cells = pg.eval_on_selector_all("#table-body tr[data-row] td:nth-child(7)",
                                    "els => els.map(e => e.textContent.trim())")
    chk("table_shows_current_name", set(cells) == {"cris"}, "| %s" % cells)

    # The blob must stay clean - _by/_at are table columns, not entry fields.
    pg.evaluate("() => { window.__p = entryPayload(entries[0]); }")
    chk("payload_strips_derived",
        pg.evaluate("() => !('_by' in window.__p) && !('_at' in window.__p) && !('id' in window.__p)"))

    chk("no_js_errors", not errs, "|" + str(errs[:3]))
    br.close()

sys.exit(chk.report())
