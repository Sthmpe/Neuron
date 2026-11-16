"""Acceptance checks for a built web app, written as plain data and run over HTTP.

A check is {"name": ..., "steps": [...]}. Steps:
  {"get": "/path", ...expectations}
  {"post": "/path", "form": {...}, ...expectations}
  {"login": {"username": ..., "password": ...}}
  {"restart": true}                      restart the app (its data must survive)
Expectations (all optional):
  "expect_status": 200 | [200, 303]      status of the final page
  "expect_redirect": "/login"            the first response must redirect there
  "expect_text": ["Ada", ...]            visible text must contain each (case-insensitive)
  "expect_no_text": [...]                visible text must contain none
  "expect_near": [["Low stock", "1"]]    the number must appear right next to the label
"""
import html
import http.cookiejar
import re
import urllib.error
import urllib.parse
import urllib.request


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def visible_text(page):
    page = re.sub(r"(?is)<(script|style).*?</\1>", " ", page)
    values = " ".join(re.findall(r'value="([^"]*)"', page))
    return html.unescape(re.sub(r"(?s)<[^>]+>", " ", page) + " " + values)


class CheckRunner:
    def __init__(self, base_url, restart=None):
        self.base_url, self.restart = base_url, restart
        self.jar = http.cookiejar.CookieJar()

    def _opener(self, follow=True):
        handlers = [urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(self.jar)]
        if not follow:
            handlers.append(_NoRedirect())
        return urllib.request.build_opener(*handlers)

    def _request(self, path, form=None, follow=True):
        data = urllib.parse.urlencode(form).encode() if form is not None else None
        try:
            r = self._opener(follow).open(self.base_url + path, data, timeout=15)
            return r.status, r.read().decode("utf-8", "replace"), r.headers.get("Location", ""), r.geturl()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace"), e.headers.get("Location", ""), self.base_url + path
        except OSError as e:
            return 0, f"no answer from the app: {e}", "", self.base_url + path

    def run(self, check):
        """Returns (passed, explanation of the first failure or '')."""
        for i, step in enumerate(check["steps"], 1):
            where = f"step {i}"
            if step.get("restart"):
                if self.restart is None:
                    continue
                self.base_url = self.restart()
                if not self.base_url:
                    return False, f"{where}: the app did not come back after a restart"
                continue
            if "login" in step:
                status, body, location, _ = self._request("/login", step["login"], follow=False)
                if status not in (301, 302, 303, 307, 308) or location.split("?")[0].endswith("/login"):
                    return False, f"{where}: logging in as {step['login'].get('username')} did not work (HTTP {status})"
                continue
            path = step.get("get") or step.get("post")
            form = step.get("form") if "post" in step else None
            what = f"{where} ({'POST' if 'post' in step else 'GET'} {path})"
            if "expect_redirect" in step:
                status, body, location, _ = self._request(path, form, follow=False)
                if status not in (301, 302, 303, 307, 308) or not location.split("?")[0].endswith(step["expect_redirect"]):
                    return False, f"{what}: expected a redirect to {step['expect_redirect']}, got HTTP {status} {location}"
                continue
            status, body, _, _ = self._request(path, form)
            want = step.get("expect_status", [200])
            want = want if isinstance(want, list) else [want]
            if status not in want:
                detail = visible_text(body)[:300].strip() if status >= 500 or status == 0 else ""
                return False, f"{what}: expected HTTP {want}, got {status}. {detail}"
            text = visible_text(body).lower()
            for needle in step.get("expect_text", []):
                if str(needle).lower() not in text:
                    return False, f"{what}: the page does not show '{needle}'"
            for first, second in step.get("expect_near", []):
                f, n = re.escape(str(first).lower()), re.escape(str(second))
                if not re.search(rf"{f}\W{{0,30}}{n}\b|\b{n}\W{{0,30}}{f}", text):
                    return False, f"{what}: expected '{first}' to show {second}"
            for needle in step.get("expect_no_text", []):
                if str(needle).lower() in text:
                    return False, f"{what}: the page shows '{needle}' but should not"
        return True, ""
