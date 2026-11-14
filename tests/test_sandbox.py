"""Isolation: what code inside the sandbox can and cannot do."""
import os
import tempfile
import unittest
from pathlib import Path

from neuron.brain.sandbox import Sandbox, SandboxUnavailable

SBX = Sandbox(timeout=10, mem_mb=128, max_procs=32)


@unittest.skipUnless(SBX.available(), "bubblewrap is not installed on this machine")
class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="neuron-sbx-ws-"))
        self.outside = Path(tempfile.mkdtemp(prefix="neuron-sbx-outside-"))
        (self.outside / "secret.txt").write_text("top secret")

    def py(self, code, **kw):
        return SBX.run(["python3", "-c", code], self.ws, **kw)

    def test_normal_code_runs_and_can_use_its_workspace(self):
        r = self.py("open('out.txt','w').write('hello'); print('done')")
        self.assertTrue(r.ok, r.output)
        self.assertEqual((self.ws / "out.txt").read_text(), "hello")

    def test_no_network(self):
        r = self.py("import socket; socket.create_connection(('1.1.1.1', 53), timeout=3)")
        self.assertNotEqual(r.exit_code, 0)
        self.assertIn("Network is unreachable", r.output)
        r = self.py("import socket; socket.getaddrinfo('example.com', 80)")
        self.assertNotEqual(r.exit_code, 0)

    def test_cannot_reach_services_on_this_machine(self):
        import socket
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        self.addCleanup(srv.close)
        r = self.py(f"import socket; socket.create_connection(('127.0.0.1', {srv.getsockname()[1]}), timeout=3)")
        self.assertNotEqual(r.exit_code, 0)

    def test_cannot_read_files_outside_the_workspace(self):
        r = self.py(f"print(open({str(self.outside / 'secret.txt')!r}).read())")
        self.assertNotEqual(r.exit_code, 0)
        self.assertNotIn("top secret", r.output)
        r = self.py("import os; print(sorted(os.listdir('/')))")
        self.assertEqual(r.output.strip(), "['bin', 'dev', 'lib', 'lib64', 'proc', 'tmp', 'usr', 'workspace']")
        for path in ("/etc/passwd", "/root", "/home", os.path.expanduser("~/.ssh")):
            self.assertNotEqual(self.py(f"import os; os.stat({path!r})").exit_code, 0, path)

    def test_cannot_write_outside_the_workspace(self):
        target = self.outside / "planted.txt"
        self.assertNotEqual(self.py(f"open({str(target)!r}, 'w').write('x')").exit_code, 0)
        self.assertFalse(target.exists())
        self.assertNotEqual(self.py("open('/usr/planted', 'w')").exit_code, 0)
        self.assertFalse(Path("/usr/planted").exists())
        r = self.py("open('/tmp/scratch', 'w').write('x'); print('tmp ok')")   # private /tmp, gone afterwards
        self.assertTrue(r.ok)
        self.assertFalse(Path("/tmp/scratch").exists())

    def test_cannot_escape_through_a_symlink(self):
        os.symlink(self.outside / "secret.txt", self.ws / "link")
        r = self.py("print(open('link').read())")
        self.assertNotIn("top secret", r.output)

    def test_environment_is_not_leaked(self):
        os.environ["NEURON_TEST_SECRET"] = "hunter2"
        self.addCleanup(os.environ.pop, "NEURON_TEST_SECRET")
        r = self.py("import os; print(sorted(os.environ))")
        self.assertNotIn("NEURON_TEST_SECRET", r.output)
        self.assertNotIn("PROXY", r.output.upper())

    def test_not_root_and_no_privileges(self):
        r = self.py("import os; print(os.getuid(), open('/proc/self/status').read().split('CapEff:')[1].split()[0])")
        self.assertEqual(r.output.split(), ["65534", "0000000000000000"])

    def test_cannot_see_other_processes(self):
        r = self.py("import os; print(len([p for p in os.listdir('/proc') if p.isdigit()]))")
        self.assertLessEqual(int(r.output), 3)

    def test_time_limit(self):
        r = self.py("import time; time.sleep(60)", timeout=1)
        self.assertTrue(r.timed_out)
        self.assertFalse(r.ok)
        self.assertLess(r.duration, 5)
        r = self.py("while True: pass", timeout=1)
        self.assertTrue(r.timed_out)

    def test_memory_limit(self):
        r = self.py("x = bytearray(600 * 1024 * 1024); print('allocated')")
        self.assertFalse(r.ok)
        self.assertNotIn("allocated", r.output)

    def test_fork_bomb_is_contained(self):
        r = self.py("import os\nwhile True:\n    os.fork()", timeout=5)
        self.assertFalse(r.ok)
        self.assertTrue(self.py("print('still fine')").ok)

    @unittest.skipUnless(SBX.has_seccomp, "libseccomp not available")
    def test_dangerous_kernel_calls_are_refused(self):
        r = self.py("import ctypes; l = ctypes.CDLL(None, use_errno=True); "
                    "print(l.unshare(0x40000000), l.mount(b'x', b'/tmp', b'tmpfs', 0, None), l.ptrace(0, 0, 0, 0))")
        self.assertEqual(r.output.split(), ["-1", "-1", "-1"])

    def test_output_is_capped(self):
        r = Sandbox(timeout=10, max_output_bytes=1000).run(["python3", "-c", "print('x' * 100000)"], self.ws)
        self.assertLess(len(r.output), 1100)
        self.assertIn("[output truncated]", r.output)

    def test_no_cgroups_left_behind(self):
        self.py("print(1)")
        self.assertEqual([d for d in os.listdir("/sys/fs/cgroup/memory") if d.startswith("neuron-sbx-")], [])


class FailClosedTests(unittest.TestCase):
    def test_refuses_to_run_without_bubblewrap(self):
        s = Sandbox()
        s.bwrap = None
        self.assertFalse(s.available())
        with self.assertRaises(SandboxUnavailable):
            s.run(["python3", "-c", "print(1)"], tempfile.mkdtemp())


if __name__ == "__main__":
    unittest.main()
