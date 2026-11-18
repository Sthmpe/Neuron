"""kit.web - the small web framework behind every NEURON-built app. Standard library only.

    from kit.web import App, redirect
    from kit import ui

    app = App("My Shop")                       # data is kept in data.db (SQLite)
    app.db.execute("CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, text TEXT)")

    @app.route("/notes", methods=["GET", "POST"], login=True)
    def notes(req):
        if req.method == "POST":
            app.db.execute("INSERT INTO notes(text) VALUES(?)", [req.form.get("text", "")])
            return redirect("/notes")
        rows = app.db.query("SELECT * FROM notes ORDER BY id DESC")
        return app.page(req, "Notes", ui.table(["Note"], [[r["text"]] for r in rows]))

    app.run()
"""
import hashlib
import hmac
import importlib
import mimetypes
import os
import pkgutil
import secrets
import sqlite3
import sys
import threading
import traceback
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import copy as _copy
from . import theme as _theme
from . import ui

STATIC = Path(__file__).resolve().parent / "static"


class Response:
    def __init__(self, body="", status=200, headers=None, content_type="text/html; charset=utf-8"):
        self.body = body.encode() if isinstance(body, str) else body
        self.status, self.headers, self.content_type = status, dict(headers or {}), content_type


def redirect(location):
    """Send the browser to another page (use after a successful POST)."""
    return Response("", 303, {"Location": location})


class Database:
    """SQLite with two calls: execute (change data) and query (read rows as dicts)."""

    def __init__(self, path):
        self.path, self.lock = str(path), threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row

    def execute(self, sql, params=()):
        with self.lock:
            return self.conn.execute(sql, list(params)).lastrowid

    def query(self, sql, params=()):
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, list(params)).fetchall()]

    def one(self, sql, params=()):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def value(self, sql, params=()):
        """First column of the first row, e.g. a COUNT(*)."""
        row = self.one(sql, params)
        return list(row.values())[0] if row else None


class Request:
    def __init__(self, method, path, query, form, cookies):
        self.method, self.path, self.query, self.form, self.cookies = method, path, query, form, cookies
        self.user = None      # username when logged in


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 50_000).hex()


class App:
    def __init__(self, name="App", db="data.db"):
        self.name = name
        self.nav = []            # [("Customers", "/customers"), ...] shown in the top bar
        self.routes = {}
        self.login_enabled = False
        self.db = Database(db)
        self.db.execute("CREATE TABLE IF NOT EXISTS kit_users(username TEXT PRIMARY KEY, salt TEXT, hash TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS kit_sessions(token TEXT PRIMARY KEY, username TEXT)")

    # ---- routing ---------------------------------------------------------
    def route(self, path, methods=("GET",), login=False):
        def wrap(fn):
            self.routes[path] = (fn, tuple(m.upper() for m in methods), login)
            return fn
        return wrap

    def load_pages(self, package="pages"):
        """Import every module in the `pages` folder and call its register(app)."""
        pkg = importlib.import_module(package)
        for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda i: i.name):
            module = importlib.import_module(f"{package}.{info.name}")
            if hasattr(module, "register"):
                module.register(self)

    def page(self, req, title, *content):
        """A full page in the shared layout: top bar with the app name, menu and log-out."""
        return ui.page(title, *content, brand=self.name, nav=self.nav,
                       user=req.user if req is not None else None, active=req.path if req is not None else "")

    # ---- login -----------------------------------------------------------
    def add_user(self, username, password):
        """Create the user if it does not exist yet."""
        if not self.db.one("SELECT 1 FROM kit_users WHERE username=?", [username]):
            salt = secrets.token_hex(8)
            self.db.execute("INSERT INTO kit_users VALUES(?,?,?)", [username, salt, _hash(password, salt)])

    def check_password(self, username, password):
        u = self.db.one("SELECT * FROM kit_users WHERE username=?", [username])
        return bool(u) and hmac.compare_digest(u["hash"], _hash(password, u["salt"]))

    def enable_login(self, after_login="/"):
        """Adds /login and /logout. Routes declared with login=True then require a logged-in user."""
        self.login_enabled = True

        @self.route("/login", methods=["GET", "POST"])
        def login(req):
            error = ""
            if req.method == "POST":
                if self.check_password(req.form.get("username", ""), req.form.get("password", "")):
                    token = secrets.token_hex(16)
                    self.db.execute("INSERT INTO kit_sessions VALUES(?,?)", [token, req.form["username"]])
                    return Response("", 303, {"Location": after_login,
                                              "Set-Cookie": f"session={token}; Path=/; HttpOnly; SameSite=Lax"})
                error = ui.alert("Wrong username or password.", "error")
            return ui.page("Log in", ui.card("Log in", error or "", ui.form(
                "/login", ui.field("Username", "username", required=True),
                ui.field("Password", "password", type="password", required=True), submit="Log in")),
                brand=self.name, narrow=True)

        @self.route("/logout", methods=["GET", "POST"])
        def logout(req):
            self.db.execute("DELETE FROM kit_sessions WHERE token=?", [req.cookies.get("session", "")])
            return Response("", 303, {"Location": "/login", "Set-Cookie": "session=; Path=/; Max-Age=0"})

    # ---- serving ---------------------------------------------------------
    def handle(self, method, raw_path, body=b"", cookie_header=""):
        url = urlparse(raw_path)
        path = url.path.rstrip("/") or "/"
        cookies = {k: v.value for k, v in SimpleCookie(cookie_header or "").items()}
        flat = lambda d: {k: v[-1] for k, v in d.items()}
        req = Request(method, path, flat(parse_qs(url.query, keep_blank_values=True)),
                      flat(parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)), cookies)
        session = self.db.one("SELECT username FROM kit_sessions WHERE token=?", [cookies.get("session", "")])
        req.user = session["username"] if session else None
        if path in ("/static/theme.css", "/static/neuron.css"):     # neuron.css: the name older checks look for
            return Response(_theme.css(_theme.load()), content_type="text/css; charset=utf-8")
        if path.startswith("/static/images/"):                        # the project's own pictures (images.json)
            pics = (Path.cwd() / "static" / "images").resolve()
            f = (pics / path[len("/static/images/"):]).resolve()
            if pics in f.parents and f.is_file():
                kind = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                return Response(f.read_bytes(), content_type=kind, headers={"Cache-Control": "max-age=3600"})
            return Response("Not found", 404)
        if path.startswith("/static/"):
            f = (STATIC / path[len("/static/"):]).resolve()
            if STATIC in f.parents and f.is_file():
                return Response(f.read_bytes(), content_type=mimetypes.guess_type(f.name)[0] or "application/octet-stream")
            return Response("Not found", 404)
        if path == "/" and "/" not in self.routes and self.nav:      # no home page: open the first page of the menu
            return redirect(self.nav[0][1])
        if path not in self.routes:
            return Response(ui.page("Not found", ui.alert("This page does not exist.", "error"),
                                    brand=self.name, nav=self.nav, user=req.user), 404)
        fn, methods, needs_login = self.routes[path]
        if method not in methods:
            return Response("Method not allowed", 405)
        if needs_login and not req.user:
            return redirect("/login")
        try:
            out = fn(req)
        except Exception:
            traceback.print_exc()
            sys.stderr.flush()
            return Response(ui.page("Error", ui.alert("Something went wrong on this page.", "error"),
                                    brand=self.name, nav=self.nav, user=req.user), 500)
        res = out if isinstance(out, Response) else Response(str(out))
        if res.content_type.startswith("text/html") and _copy.has_dash(res.body.decode("utf-8", "replace")):
            res.body = _copy.no_dashes(res.body.decode("utf-8")).encode()     # last safety net: never an em dash
        return res

    def run(self, port=None, host="127.0.0.1"):
        app = self
        port = int(port or os.environ.get("PORT", 8000))

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _do(self):
                n = int(self.headers.get("Content-Length") or 0)
                res = app.handle(self.command, self.path, self.rfile.read(n) if n else b"", self.headers.get("Cookie", ""))
                self.send_response(res.status)
                self.send_header("Content-Type", res.content_type)
                self.send_header("Content-Length", str(len(res.body)))
                for k, v in res.headers.items():
                    self.send_header(k, v)
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(res.body)

            do_GET = do_POST = do_HEAD = _do

        server = ThreadingHTTPServer((host, port), Handler)
        print(f"{self.name} running on http://{host}:{port}", flush=True)
        server.serve_forever()
