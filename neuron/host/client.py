"""Tiny HTTP+JSON client the host uses to talk to the brain."""
import json
import urllib.error
import urllib.request


class BrainUnreachable(Exception):
    pass


class HostClient:
    def __init__(self, url="http://127.0.0.1:8765", timeout=5):
        self.url, self.timeout = url.rstrip("/"), timeout
        # talk to the brain directly, never through a system proxy
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _req(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data, {"Content-Type": "application/json"}, method=method)
        try:
            with self._opener.open(req, timeout=self.timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            return json.loads(e.read() or b"{}")
        except (urllib.error.URLError, OSError) as e:
            raise BrainUnreachable(str(e)) from e

    def health(self):
        return self._req("GET", "/health")

    def send_task(self, goal, delay_seconds=0):
        return self._req("POST", "/tasks", {"goal": goal, "delay_seconds": delay_seconds})

    def tasks(self):
        return self._req("GET", "/tasks")["tasks"]

    def task(self, task_id):
        return self._req("GET", f"/tasks/{task_id}")

    def events(self, task_id, after=0):
        return self._req("GET", f"/tasks/{task_id}/events?after={after}")["events"]

    def report(self, task_id):
        return self._req("GET", f"/tasks/{task_id}/report")

    def permissions(self, status="pending"):
        return self._req("GET", f"/permissions?status={status}")["permissions"]

    def decide(self, perm_id, approve):
        return self._req("POST", f"/permissions/{perm_id}", {"decision": "approve" if approve else "reject"})

    def set_network(self, online):
        return self._req("POST", "/network", {"online": online})

    def network(self):
        return self._req("GET", "/network")
