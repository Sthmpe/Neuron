"""Isolated runner for code the brain did not write itself (model-generated code, project tests).

Built on bubblewrap (`bwrap`), Linux namespaces, cgroups and seccomp. One call = one
throw-away sandbox. Inside it the code:

  * has NO network: a new, empty network namespace (not even working loopback traffic to the host)
  * sees ONLY its workspace folder (read-write, mounted at /workspace), a private empty /tmp,
    and the operating system's /usr (read-only, needed to run Python at all).
    /home, /root, /etc, /var and every other folder of the machine do not exist inside.
  * is not root: runs as user 'nobody' in its own user namespace with every capability dropped
    and "no new privileges" set
  * cannot see or signal other processes (own process-ID namespace)
  * gets none of the brain's environment variables
  * is killed when it runs longer than the time limit
  * is killed when it uses more memory than the limit (memory cgroup; address-space limit as fallback)
  * can start only a limited number of processes (pids cgroup) and write only limited-size files
  * cannot call a list of dangerous kernel functions (seccomp filter), when libseccomp is present

If bubblewrap is missing the sandbox REFUSES to run anything (fails closed) - it never
falls back to running generated code unprotected.
"""
import ctypes
import ctypes.util
import os
import resource
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

CGROUP_ROOT = Path("/sys/fs/cgroup")
DENIED_SYSCALLS = [
    "ptrace", "mount", "umount2", "pivot_root", "chroot", "unshare", "setns", "kexec_load",
    "kexec_file_load", "init_module", "finit_module", "delete_module", "bpf", "perf_event_open",
    "keyctl", "add_key", "request_key", "reboot", "swapon", "swapoff", "open_by_handle_at",
    "name_to_handle_at", "process_vm_readv", "process_vm_writev", "userfaultfd", "io_uring_setup",
    "io_uring_enter", "io_uring_register", "acct", "settimeofday", "clock_settime", "adjtimex",
    "mknod", "mknodat", "quotactl", "syslog", "vhangup", "move_mount", "open_tree", "fsopen",
    "fsmount", "fsconfig", "mount_setattr",
]
CLONE_NS_FLAGS = [0x00020000, 0x02000000, 0x04000000, 0x08000000, 0x10000000, 0x20000000, 0x40000000]


def _own_cgroup(controller):
    try:
        for line in open("/proc/self/cgroup"):
            _, ctrls, path = line.strip().split(":", 2)
            if controller in ctrls.split(","):
                return CGROUP_ROOT / controller / path.lstrip("/")
    except OSError:
        pass
    return CGROUP_ROOT / controller


class SandboxUnavailable(Exception):
    pass


@dataclass
class SandboxResult:
    exit_code: int
    output: str
    timed_out: bool
    oom_killed: bool
    duration: float
    peak_mem_bytes: int

    @property
    def ok(self):
        return self.exit_code == 0 and not self.timed_out and not self.oom_killed


class _ArgCmp(ctypes.Structure):
    _fields_ = [("arg", ctypes.c_uint), ("op", ctypes.c_int),
                ("datum_a", ctypes.c_uint64), ("datum_b", ctypes.c_uint64)]


def _seccomp_filter_fd():
    """Build the seccomp filter and return a readable fd holding the BPF program, or None."""
    name = ctypes.util.find_library("seccomp") or "libseccomp.so.2"
    try:
        lib = ctypes.CDLL(name, use_errno=True)
    except OSError:
        return None
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint,
                                           ctypes.POINTER(_ArgCmp)]
    lib.seccomp_export_bpf.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    allow, eperm, enosys = 0x7FFF0000, 0x00050000 | 1, 0x00050000 | 38
    ctx = lib.seccomp_init(allow)
    if not ctx:
        return None
    try:
        for sc in DENIED_SYSCALLS:
            nr = lib.seccomp_syscall_resolve_name(sc.encode())
            if nr >= 0:
                lib.seccomp_rule_add(ctx, eperm, nr, 0)
        nr = lib.seccomp_syscall_resolve_name(b"clone3")   # flags are hidden in a struct: refuse,
        if nr >= 0:                                        # libc then falls back to clone()
            lib.seccomp_rule_add(ctx, enosys, nr, 0)
        nr = lib.seccomp_syscall_resolve_name(b"clone")
        for flag in CLONE_NS_FLAGS:                        # no new namespaces from inside
            cmp = _ArgCmp(0, 7, flag, flag)                # SCMP_CMP_MASKED_EQ
            lib.seccomp_rule_add_array(ctx, eperm, nr, 1, ctypes.byref(cmp))
        fd = os.memfd_create("neuron-seccomp")
        if lib.seccomp_export_bpf(ctx, fd) != 0:
            os.close(fd)
            return None
        os.lseek(fd, 0, os.SEEK_SET)
        return fd
    finally:
        lib.seccomp_release(ctx)


class _Cgroup:
    """A memory + pids cgroup (v1) for one sandbox run. Silently unavailable on other systems."""

    def __init__(self, mem_bytes, max_procs):
        self.dirs = {}
        name = "neuron-sbx-" + uuid.uuid4().hex[:12]
        try:
            # nested inside whatever memory cgroup we are in, so a RAM tier also counts the sandbox
            m = _own_cgroup("memory") / name
            m.mkdir()
            (m / "memory.limit_in_bytes").write_text(str(mem_bytes))
            try:
                (m / "memory.memsw.limit_in_bytes").write_text(str(mem_bytes))
            except OSError:
                pass
            self.dirs["memory"] = m
        except OSError:
            pass
        try:
            p = _own_cgroup("pids") / name
            p.mkdir()
            (p / "pids.max").write_text(str(max_procs))
            self.dirs["pids"] = p
        except OSError:
            pass

    def enter(self):  # runs in the child, before bwrap starts
        for d in self.dirs.values():
            with open(d / "cgroup.procs", "w") as f:
                f.write(str(os.getpid()))

    def peak(self):
        try:
            return int((self.dirs["memory"] / "memory.max_usage_in_bytes").read_text())
        except (KeyError, OSError, ValueError):
            return 0

    def oom(self):
        try:
            text = (self.dirs["memory"] / "memory.oom_control").read_text()
            for line in text.splitlines():
                if line.startswith("oom_kill "):
                    return int(line.split()[1]) > 0
            return int((self.dirs["memory"] / "memory.failcnt").read_text()) > 0
        except (KeyError, OSError, ValueError):
            return False

    def close(self):
        for d in self.dirs.values():
            for _ in range(50):
                try:
                    pids = d.joinpath("cgroup.procs").read_text().split()
                    for pid in pids:
                        try:
                            os.kill(int(pid), signal.SIGKILL)
                        except OSError:
                            pass
                    d.rmdir()
                    break
                except OSError:
                    time.sleep(0.02)


class Sandbox:
    def __init__(self, timeout=60, mem_mb=512, max_procs=64, max_file_mb=32, max_output_bytes=200_000, toolchains=False):
        """toolchains=True also mounts installed compilers read-only (g++/clang via /etc/alternatives, Go, Rust,
        Node, Java) so compiled-language projects can be built and tested. Off by default: same as before."""
        self.toolchains = toolchains
        self.timeout, self.mem_mb, self.max_procs = timeout, mem_mb, max_procs
        self.max_file_mb, self.max_output_bytes = max_file_mb, max_output_bytes
        self.bwrap = shutil.which("bwrap")
        self.has_memcg = os.access(CGROUP_ROOT / "memory", os.W_OK) and \
            (CGROUP_ROOT / "memory" / "memory.limit_in_bytes").exists()
        self.has_pidcg = os.access(CGROUP_ROOT / "pids", os.W_OK)
        fd = _seccomp_filter_fd()
        self.has_seccomp = fd is not None
        if fd is not None:
            os.close(fd)

    def available(self):
        return self.bwrap is not None

    def describe(self):
        return {
            "engine": "bubblewrap (Linux namespaces)" if self.bwrap else "NONE - refuses to run code",
            "network": "none (empty network namespace)",
            "filesystem": "workspace read-write; /usr read-only; private /tmp; nothing else exists",
            "user": "nobody (uid 65534) in a user namespace, all capabilities dropped, no-new-privileges",
            "processes": "own PID namespace",
            "time_limit_s": self.timeout,
            "memory_limit_mb": self.mem_mb,
            "memory_limit_by": "memory cgroup" if self.has_memcg else "address-space rlimit (weaker)",
            "process_limit": self.max_procs if self.has_pidcg else "not enforced (no pids cgroup)",
            "seccomp_filter": self.has_seccomp,
        }

    def _bwrap(self, workspace, extra=()):
        if not self.bwrap:
            raise SandboxUnavailable("bubblewrap (bwrap) is not installed; refusing to run code unsandboxed")
        workspace = str(Path(workspace).resolve())
        tc = self._toolchain_args() if self.toolchains else []
        return [self.bwrap, "--unshare-all", "--unshare-user", "--uid", "65534", "--gid", "65534",
               "--die-with-parent", "--new-session", "--cap-drop", "ALL", "--hostname", "sandbox",
               "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
               "--symlink", "usr/bin", "/bin", "--proc", "/proc", "--dev", "/dev",
               "--size", str(64 * 1024 * 1024), "--tmpfs", "/tmp",
               "--bind", workspace, "/workspace", "--chdir", "/workspace",
               "--clearenv", "--setenv", "PATH", "/usr/local/bin:/usr/bin", "--setenv", "HOME", "/workspace",
               "--setenv", "LANG", "C.UTF-8", "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
               "--setenv", "PYTHONHASHSEED", "0"] + tc + list(extra)

    def run(self, argv, workspace, timeout=None):
        timeout = timeout or self.timeout
        mem_bytes = self.mem_mb * 1024 * 1024
        cmd = self._bwrap(workspace)
        pass_fds = ()
        sfd = _seccomp_filter_fd()
        if sfd is not None:
            cmd += ["--seccomp", str(sfd)]
            pass_fds = (sfd,)
        cmd += ["--"] + list(argv)
        cg = _Cgroup(mem_bytes, self.max_procs)
        use_rlimit_as = "memory" not in cg.dirs

        def preexec():
            cg.enter()
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            fs = self.max_file_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_FSIZE, (fs, fs))
            resource.setrlimit(resource.RLIMIT_CPU, (int(timeout) + 5, int(timeout) + 5))
            if use_rlimit_as:
                resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

        start = time.time()
        timed_out = False
        with tempfile.TemporaryFile() as out:
            try:
                proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                        preexec_fn=preexec, pass_fds=pass_fds, cwd="/")
                try:
                    code = proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    proc.kill()
                    code = proc.wait()
            finally:
                if sfd is not None:
                    os.close(sfd)
                peak, oom = cg.peak(), cg.oom()
                cg.close()
            out.seek(0)
            data = out.read(self.max_output_bytes + 1)
        text = data[: self.max_output_bytes].decode("utf-8", "replace")
        if len(data) > self.max_output_bytes:
            text += "\n[output truncated]"
        return SandboxResult(code, text, timed_out, oom, time.time() - start, peak)

    def start(self, argv, workspace, port=8000):
        """Start a long-running program (a web app) in the sandbox and make its port reachable
        from this machine WITHOUT giving the sandbox any network: connections travel over a
        Unix socket in a shared folder. Returns a SandboxedServer; call .stop() when done."""
        sockdir = tempfile.mkdtemp(prefix="nrn-")
        relay = str(Path(__file__).resolve().with_name("sandbox_relay.py"))
        cmd = self._bwrap(workspace, ["--bind", sockdir, "/run/neuron", "--ro-bind", relay, "/neuron_relay.py",
                                      "--setenv", "PYTHONUNBUFFERED", "1"])
        pass_fds = ()
        sfd = _seccomp_filter_fd()
        if sfd is not None:
            cmd += ["--seccomp", str(sfd)]
            pass_fds = (sfd,)
        cmd += ["--", "python3", "/neuron_relay.py", "/run/neuron/app.sock", str(port), "--"] + list(argv)
        mem_bytes = self.mem_mb * 1024 * 1024
        cg = _Cgroup(mem_bytes, self.max_procs)

        def preexec():
            cg.enter()
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            fs = self.max_file_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_FSIZE, (fs, fs))

        out = tempfile.TemporaryFile()
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                    preexec_fn=preexec, pass_fds=pass_fds, cwd="/")
        finally:
            if sfd is not None:
                os.close(sfd)
        return SandboxedServer(proc, cg, sockdir, out, self.max_output_bytes)


class SandboxedServer:
    def __init__(self, proc, cg, sockdir, out, max_output):
        self.proc, self.cg, self.sockdir, self.out, self.max_output = proc, cg, sockdir, out, max_output
        self.sock_path = os.path.join(sockdir, "app.sock")
        self._listener = socket.socket()
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(64)
        self.port = self._listener.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self._closed = False
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while not self._closed:
            try:
                conn, _ = self._listener.accept()
            except OSError:
                return
            try:
                up = socket.socket(socket.AF_UNIX)
                up.connect(self.sock_path)
            except OSError:
                conn.close()
                continue
            for a, b in ((conn, up), (up, conn)):
                threading.Thread(target=self._pump, args=(a, b), daemon=True).start()

    @staticmethod
    def _pump(a, b):
        try:
            while True:
                data = a.recv(65536)
                if not data:
                    break
                b.sendall(data)
        except OSError:
            pass
        finally:
            for s in (a, b):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                s.close()

    def alive(self):
        return self.proc.poll() is None

    def wait_ready(self, path="/", timeout=15):
        """True once the app answers HTTP. False if it died or never answered."""
        import urllib.error
        import urllib.request
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        end = time.time() + timeout
        while time.time() < end and self.alive():
            if os.path.exists(self.sock_path):
                try:
                    opener.open(self.url + path, timeout=3).read()
                    return True
                except urllib.error.HTTPError:
                    return True
                except OSError:
                    pass
            time.sleep(0.1)
        return False

    def output(self):
        self.out.flush()
        self.out.seek(0)
        return self.out.read(self.max_output).decode("utf-8", "replace")

    def peak_mem_bytes(self):
        return self.cg.peak()

    def stop(self):
        if self._closed:
            return self.output()
        self._closed = True
        try:
            self._listener.close()
        except OSError:
            pass
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait()
        text = self.output()
        self.cg.close()
        self.out.close()
        shutil.rmtree(self.sockdir, ignore_errors=True)
        return text


TOOLCHAIN_DIRS = ["/etc/alternatives", "/usr/local/go", "/opt/node22", "/root/.cargo", "/root/.rustup"]
TOOLCHAIN_PATH = "/usr/local/go/bin:/opt/node22/bin:/root/.cargo/bin:/usr/local/bin:/usr/bin"


def _toolchain_args(self):
    args = []
    for d in TOOLCHAIN_DIRS:
        if os.path.isdir(d) and not d.startswith("/usr/"):
            args += ["--ro-bind", d, d]
    return args + ["--setenv", "PATH", TOOLCHAIN_PATH, "--setenv", "GOTOOLCHAIN", "local", "--setenv", "GOFLAGS", "-mod=mod",
                   "--setenv", "CARGO_HOME", "/workspace/.cargo", "--setenv", "RUSTUP_HOME", "/root/.rustup",
                   "--setenv", "GOCACHE", "/workspace/.cache/go", "--setenv", "GOPATH", "/workspace/.gopath"]


Sandbox._toolchain_args = _toolchain_args
