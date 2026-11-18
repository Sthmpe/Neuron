"""Installer: tier choice with room for the system, resumable download, checksum refusal, plan mode."""
import hashlib
import http.server
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from neuron import install

GIB = install.GIB


class Ranged(http.server.SimpleHTTPRequestHandler):
    cut_once = {"done": False}

    def log_message(self, *a):
        pass

    def do_GET(self):
        data = Path(self.directory, self.path.lstrip("/")).read_bytes()
        start = 0
        if self.headers.get("Range"):
            start = int(self.headers["Range"].split("=")[1].split("-")[0])
            self.send_response(206)
        else:
            self.send_response(200)
        body = data[start:]
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not self.cut_once["done"] and start == 0:       # first try: the connection drops halfway
            self.cut_once["done"] = True
            self.wfile.write(body[: len(body) // 2])
            self.wfile.flush()
            self.connection.shutdown(2)
            return
        self.wfile.write(body)


class InstallTests(unittest.TestCase):
    def test_tier_keeps_room_for_the_system(self):
        tiers = ["2gb", "4gb", "8gb"]
        self.assertEqual(install.choose_tier(16 * GIB, tiers)[0], "8gb")
        self.assertEqual(install.choose_tier(8 * GIB, tiers)[0], "4gb")      # 8 GB machine cannot give all 8 GB to NEURON
        self.assertEqual(install.choose_tier(4 * GIB, tiers)[0], "2gb")
        with self.assertRaises(install.InstallError):
            install.choose_tier(2 * GIB, tiers)
        self.assertEqual(install.choose_tier(64 * GIB, ["2gb", "4gb"])[0], "4gb")   # only frozen tiers

    def test_download_resumes_and_checks(self):
        d = Path(tempfile.mkdtemp())
        (d / "srv").mkdir()
        blob = os.urandom(3 * 1024 * 1024)
        (d / "srv" / "m.gguf").write_bytes(blob)
        handler = lambda *a, **k: Ranged(*a, directory=str(d / "srv"), **k)
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.shutdown)
        url = f"http://127.0.0.1:{httpd.server_address[1]}/m.gguf"
        old = {k: os.environ.pop(k) for k in list(os.environ) if "proxy" in k.lower()}
        self.addCleanup(os.environ.update, old)
        logs = []
        sha = install.download(url, d / "m.gguf", hashlib.sha256(blob).hexdigest(), log=logs.append, wait=0)
        self.assertEqual((d / "m.gguf").read_bytes(), blob)
        self.assertTrue(any("resuming" in l for l in logs), logs)
        with self.assertRaises(install.InstallError):
            install.download(url, d / "bad.gguf", "0" * 64, log=logs.append, wait=0)
        self.assertFalse((d / "bad.gguf").exists())
        self.assertFalse((d / "bad.gguf.part").exists())

    def test_plan_mode_changes_nothing(self):
        d = Path(tempfile.mkdtemp())
        frozen = {"tiers": {"2gb": {"id": "x", "file": "x.gguf", "sha256": "a" * 64, "source": "http://example.invalid/x.gguf",
                                    "bytes": GIB, "licence": "apache-2.0"}}}
        (d / "frozen.json").write_text(json.dumps(frozen))
        self.assertEqual(install.main(["--home", str(d / "home"), "--frozen", str(d / "frozen.json"), "--tier", "2gb", "--plan"]), 0)
        self.assertFalse((d / "home").exists())


class WindowsPlanTests(unittest.TestCase):
    def test_memory_limit_leaves_room_for_windows_and_picks_the_tier(self):
        w = install.windows_plan
        self.assertEqual(w(8, 19045)["wsl_memory_gb"], 5)            # Windows 10 laptop with 8 GB
        self.assertEqual(w(8, 19045)["tier"], "4gb")
        self.assertEqual(w(8, 19045)["networking"], "port forwarding")
        self.assertEqual(w(16, 22631, "2.3.26")["tier"], "8gb")       # Windows 11 23H2, 16 GB
        self.assertEqual(w(16, 22631, "2.3.26")["networking"], "mirrored")
        self.assertEqual(w(16, 22000, "2.3.26")["networking"], "port forwarding")   # Windows 11 21H2: no mirrored mode
        self.assertEqual(w(16, 22631, "1.2.5")["networking"], "port forwarding")    # old WSL
        self.assertEqual(w(6, 22631)["tier"], "2gb")
        self.assertFalse(w(4, 22631)["ok"])                             # 4 GB: not enough beside Windows
        self.assertFalse(w(16, 18363)["ok"])                            # too old for WSL2

    def test_powershell_script_uses_the_same_numbers(self):
        text = (Path(__file__).resolve().parents[1] / "scripts" / "install-windows.ps1").read_text()
        for needle in ("[math]::Max(3, [math]::Ceiling($ramGB * 0.30))", "$wslGB * 0.15", "$build -ge 22621", "$wslMajor -ge 2",
                       "-lt 19041", "$wslGB -lt 3"):
            self.assertIn(needle, text)
        self.assertNotIn("\u2014", text)


if __name__ == "__main__":
    unittest.main()
