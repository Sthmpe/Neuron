"""NEURON's local server. The phone pairs once, then sends goals and files and watches the work.

  python3 -m neuron.server [--host 0.0.0.0] [--port 8642] [--home ~/.neuron] [--tier 4gb]
  python3 -m neuron.server code        # print a fresh pairing code (asks the running server, from this machine only)
"""
import http.client
import json
import mimetypes
import os
import re
import secrets
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import sysinfo
from .auth import Pairing

UI = Path(__file__).resolve().parent / "ui"
FONTS = Path(__file__).resolve().parents[1] / "kit_next" / "static" / "fonts"
MAX_UPLOAD = 200 * 1024 * 1024


class Previews:
    """Shows a built web app on its own port, behind a one-time token (its links expect to be at '/')."""

    def __init__(self, host, sandbox_factory):
        self.host, self.sandbox_factory, self.running = host, sandbox_factory, {}

    def open(self, jid, app_dir):
        if jid in self.running:
            return self.running[jid]["url"]
        srv = self.sandbox_factory().start(["python3", "app.py"], app_dir)
        if not srv.wait_ready("/"):
            srv.stop()
            return None
        token, upstream = secrets.token_urlsafe(16), srv

        class Proxy(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _go(self):
                cookies = {k: v.value for k, v in SimpleCookie(self.headers.get("Cookie", "")).items()}
                q = parse_qs(urlparse(self.path).query)
                set_cookie = None
                if cookies.get("neuron_preview") != token:
                    if q.get("neuron_preview", [""])[0] != token:
                        self.send_response(403); self.end_headers(); self.wfile.write(b"Open the preview from NEURON."); return
                    set_cookie = f"neuron_preview={token}; Path=/; HttpOnly; SameSite=Lax"
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else None
                c = http.client.HTTPConnection("127.0.0.1", upstream.port, timeout=30)
                hdrs = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "connection")}
                c.request(self.command, re.sub(r"[?&]neuron_preview=[^&]*", "", self.path) or "/", body, hdrs)
                r = c.getresponse()
                data = r.read()
                self.send_response(r.status)
                for k, v in r.getheaders():
                    if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                        self.send_header(k, v)
                if set_cookie:
                    self.send_header("Set-Cookie", set_cookie)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            do_GET = do_POST = _go

        httpd = ThreadingHTTPServer((self.host, 0), Proxy)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.running[jid] = {"server": srv, "httpd": httpd, "url": f":{httpd.server_address[1]}/?neuron_preview={token}"}
        return self.running[jid]["url"]

    def close_all(self):
        for p in self.running.values():
            p["httpd"].shutdown()
            p["server"].stop()
        self.running.clear()


def make_handler(state):
    jobs, pairing = state["jobs"], state["pairing"]

    class H(BaseHTTPRequestHandler):
        server_version = "NEURON"

        def log_message(self, *a):
            pass

        # ---- plumbing ---------------------------------------------------------------------------------
        def _send(self, code, body, ctype="application/json", headers=None):
            data = body if isinstance(body, bytes) else (json.dumps(body) if ctype == "application/json" else body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def _token(self):
            auth = self.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                return auth[7:]
            return {k: v.value for k, v in SimpleCookie(self.headers.get("Cookie", "")).items()}.get("neuron_token")

        def _device(self):
            return pairing.check(self._token())

        def _local(self):
            return self.client_address[0] in ("127.0.0.1", "::1")

        def _body(self, limit=1_000_000):
            n = int(self.headers.get("Content-Length") or 0)
            if n > limit:
                raise ValueError("too large")
            return self.rfile.read(n) if n else b""

        def _json(self):
            try:
                return json.loads(self._body() or b"{}")
            except ValueError:
                return {}

        # ---- routes -----------------------------------------------------------------------------------
        def do_GET(self):
            u = urlparse(self.path)
            path, q = u.path, parse_qs(u.query)
            if path in ("/", "/index.html"):
                return self._send(200, (UI / "index.html").read_bytes(), "text/html; charset=utf-8")
            if path.startswith("/ui/") or path.startswith("/fonts/"):
                base = UI if path.startswith("/ui/") else FONTS
                f = (base / path.split("/", 2)[2]).resolve()
                if base.resolve() in f.parents and f.is_file():
                    return self._send(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream",
                                      {"Cache-Control": "max-age=3600"})
                return self._send(404, {"error": "not found"})
            if path == "/api/me":
                d = self._device()
                return self._send(200, {"paired": bool(d), "name": d["name"] if d else None})
            if path == "/local/pair-code" and self._local():
                return self._send(200, {"code": pairing.new_code(), "valid_minutes": 10})
            if not self._device():
                return self._send(401, {"error": "pair this device first"})
            if path == "/api/status":
                return self._send(200, state["status"]())
            if path == "/api/jobs":
                return self._send(200, {"jobs": jobs.all()[:50]})
            m = re.fullmatch(r"/api/jobs/([\w-]+)(/events|/file)?", path)
            if m:
                try:
                    if m.group(2) == "/events":
                        return self._send(200, {"events": jobs.events(m.group(1), int(q.get("after", ["0"])[0]))})
                    if m.group(2) == "/file":
                        f = jobs.file(m.group(1), q.get("path", [""])[0])
                        return self._send(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream",
                                          {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(f.name)}"})
                    return self._send(200, jobs.detail(m.group(1)))
                except KeyError:
                    return self._send(404, {"error": "not found"})
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            path = urlparse(self.path).path
            if path == "/api/pair":
                body = self._json()
                token = pairing.pair(body.get("code", ""), body.get("name", "phone"))
                if not token:
                    return self._send(403, {"error": "wrong or expired code"})
                return self._send(200, {"paired": True}, headers={"Set-Cookie": f"neuron_token={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000"})
            if not self._device():
                return self._send(401, {"error": "pair this device first"})
            if self.headers.get("X-Neuron") != "1":               # blocks forms posted from other websites
                return self._send(403, {"error": "missing X-Neuron header"})
            try:
                if path == "/api/jobs":
                    goal = str(self._json().get("goal", "")).strip()
                    if not goal:
                        return self._send(400, {"error": "say what you want done"})
                    return self._send(201, {"id": jobs.create(goal)})
                m = re.fullmatch(r"/api/jobs/([\w-]+)/(upload|start|stop|approve|preview)", path)
                if not m:
                    return self._send(404, {"error": "not found"})
                jid, act = m.groups()
                if act == "upload":
                    name = parse_qs(urlparse(self.path).query).get("name", ["file"])[0]
                    jobs.add_file(jid, name, self._body(MAX_UPLOAD))
                    return self._send(200, {"ok": True})
                if act == "start":
                    jobs.start(jid)
                elif act == "stop":
                    jobs.stop(jid)
                elif act == "approve":
                    b = self._json()
                    jobs.approve(jid, b["task"], b["action"], bool(b.get("approve")))
                elif act == "preview":
                    app_dir = jobs.file(jid, "app/app.py").parent
                    url = state["previews"].open(jid, app_dir)
                    return self._send(200, {"url": url} if url else {"error": "the app did not start"})
                return self._send(200, {"ok": True})
            except KeyError:
                return self._send(404, {"error": "not found"})
            except ValueError as e:
                return self._send(400, {"error": str(e)})

    return H


def serve(home, host, port, runner_factory, sandbox_factory, registry=None, models_status=lambda: {}, log=print):
    from .jobs import JobManager
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    jobs = JobManager(home, runner_factory, sandbox_factory, registry, log=log)
    pairing = Pairing(home)
    previews = Previews(host, sandbox_factory)
    started = time.time()

    def status():
        r = jobs.runner
        return {"memory": sysinfo.memory(), "load": sysinfo.load(), "online": sysinfo.online(), "uptime_s": round(time.time() - started),
                "models": models_status(), "loaded_model": getattr(r, "loaded", None) if r else None,
                "current_job": jobs.current, "queue": list(jobs.queue)}

    state = {"jobs": jobs, "pairing": pairing, "previews": previews, "status": status}
    httpd = ThreadingHTTPServer((host, port), make_handler(state))
    httpd.neuron = state
    return httpd
