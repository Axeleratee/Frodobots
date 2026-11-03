"""Shared Playwright harness: build a testable page and drive the app.

The app is a single static file, so a test "build" is just index.html with the
Supabase CDN script swapped for the mock and config.js inlined.
"""
import datetime
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILD = pathlib.Path("/tmp/claude-0/appbuild")

ADMIN = "uid-boss@robotqa.local"
CRIS = "uid-cris@robotqa.local"
ANA = "uid-ana@robotqa.local"

PROFILES = {
    ADMIN: {"name": "boss", "email": "boss@robotqa.local", "role": "admin"},
    CRIS: {"name": "cris", "email": "cris@robotqa.local", "role": "editor"},
    ANA: {"name": "ana", "email": "ana@robotqa.local", "role": "viewer"},
}


def build(name="app.html", config=None):
    """Write a self-contained test page and return its file:// URL.

    `config` overrides keys in window.APP_CONFIG, so a setting can be tested
    the way a real deployment sets it rather than by poking at globals.
    """
    BUILD.mkdir(parents=True, exist_ok=True)
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    mock = (ROOT / "test" / "mock.js").read_text(encoding="utf-8")
    cfg = (ROOT / "config.js").read_text(encoding="utf-8")

    html, n = re.subn(
        r'<script src="https://cdn\.jsdelivr\.net/npm/@supabase[^"]*"></script>',
        "<script>" + mock.replace("\\", "\\\\") + "</script>", html, count=1)
    assert n == 1, "supabase CDN script tag not found - did index.html change?"

    # Overrides go INSIDE the config script, not before </head>: the page has
    # no </head>, and injecting earlier would touch window.APP_CONFIG before
    # config.js has defined it.
    if config:
        import json
        cfg += "\nObject.assign(window.APP_CONFIG, %s);" % json.dumps(config)

    html, n = re.subn(r'<script src="config\.js"></script>',
                      "<script>" + cfg + "</script>", html, count=1)
    assert n == 1, "config.js script tag not found"

    # Google Fonts is blocked in this sandbox; dropping it avoids proxy noise.
    html = re.sub(r"<link[^>]*fonts\.googleapis\.com[^>]*>", "", html)

    out = BUILD / name
    out.write_text(html, encoding="utf-8")
    return "file://" + str(out)


def seed(page, observations=None, assignments=None, options=None,
         profiles=None, missing=()):
    """Load fixtures into localStorage, then reload so the app reads them."""
    page.evaluate(
        """([obs, asg, opt, prof, miss]) => {
          localStorage.setItem('__mock_table', JSON.stringify(obs));
          localStorage.setItem('__mock_assignments', JSON.stringify(asg));
          localStorage.setItem('__mock_options', JSON.stringify(opt));
          localStorage.setItem('__mock_profiles', JSON.stringify(prof));
          localStorage.setItem('__mock_reports', '[]');
          localStorage.setItem('__mock_audit', '[]');
          miss.forEach(m => localStorage.setItem('__mock_' + m + '_missing', '1'));
        }""",
        [observations or [], assignments or [], options or [],
         profiles or PROFILES, list(missing)])
    page.reload()


def login(page, user="boss", timeout=9000):
    page.fill("#auth-username", user)
    page.fill("#auth-password", "x")
    page.click("#auth-submit")
    page.wait_for_selector("#card-log", state="visible", timeout=timeout)
    page.wait_for_timeout(700)


def obs(oid, date, robot, by=ADMIN, tasks=("sweep floor",), issues=("none",),
        no_data=False, late=False, severity=0, logged_at=None):
    """One observations row, shaped the way the database stores it."""
    name = PROFILES.get(by, {}).get("name", "")
    return {
        "id": oid,
        "created_at": (logged_at or date + "T09:00:00Z"),
        "created_by": by,
        "entry": {
            "id": oid, "date": date, "robot": robot,
            "task": [] if no_data else list(tasks),
            "issue": ["nodata"] if no_data else list(issues),
            "severity": "" if no_data else severity,
            "notes": "", "loggedBy": name, "links": [],
            "noData": no_data, "lateUpload": late,
        },
    }


def assign(aid, user_id, robot, starts_on, ends_on=None):
    return {"id": aid, "user_id": user_id, "robot": robot,
            "starts_on": starts_on, "ends_on": ends_on,
            "created_at": starts_on + "T00:00:00Z", "created_by": ADMIN,
            "note": None}


def days_ago(n):
    return (datetime.date.today() - datetime.timedelta(days=n)).isoformat()


def watch_errors(page, sink):
    """Collect real JS errors, ignoring sandbox-only network noise.

    The app calls a Supabase Edge Function for AI reports and login activity.
    That host is unreachable from the test sandbox, so the browser logs a
    resource failure that says nothing about the code under test. Genuine
    exceptions and console errors still land in `sink`.
    """
    NOISE = ("ERR_TUNNEL_CONNECTION_FAILED", "Failed to load resource",
             "ERR_NAME_NOT_RESOLVED", "ERR_INTERNET_DISCONNECTED",
             "net::ERR_", "fonts.googleapis.com")

    def on_console(m):
        if m.type == "error" and not any(n in m.text for n in NOISE):
            sink.append("console: " + m.text)

    page.on("pageerror", lambda e: sink.append("pageerror: " + str(e)))
    page.on("console", on_console)


class Checks:
    """Tiny assertion collector so a run reports every failure, not just the first."""

    def __init__(self):
        self.rows = []

    def __call__(self, name, cond, extra=""):
        self.rows.append((name, bool(cond)))
        print(("PASS " if cond else "FAIL ") + name, extra)
        return bool(cond)

    def report(self):
        bad = [n for n, ok in self.rows if not ok]
        if bad:
            print("FAILED %d/%d: %s" % (len(bad), len(self.rows), ", ".join(bad)))
            return 1
        print("ALL PASS (%d/%d)" % (len(self.rows), len(self.rows)))
        return 0
