"""RAM tiers: a hard limit on TOTAL memory for everything NEURON runs.

A tier is a Linux memory cgroup. The process that enters a tier, and every process it
starts afterwards (model server, sandboxes, dev server, browser, tools), is counted
against one limit. Swap is included in the limit, so nothing can hide there. When the
limit is exceeded the kernel kills a process inside the tier - the work then fails
honestly instead of quietly using more memory than the tier has.

What this does not cover: the operating system's own memory and the kernel. A real
2 GB device also has to fit its OS in those 2 GB; this limit covers NEURON's processes only.
"""
import os
import threading
import time
from pathlib import Path

GIB = 1024 ** 3
TIERS = {"2gb": 2 * GIB, "4gb": 4 * GIB, "8gb": 8 * GIB}
MEMCG = Path("/sys/fs/cgroup/memory")


def own_cgroup(controller="memory"):
    """Path of the cgroup this process is in, for the given v1 controller."""
    try:
        for line in open("/proc/self/cgroup"):
            _, ctrls, path = line.strip().split(":", 2)
            if controller in ctrls.split(","):
                return Path("/sys/fs/cgroup") / controller / path.lstrip("/")
    except OSError:
        pass
    return Path("/sys/fs/cgroup") / controller


class TierUnavailable(Exception):
    pass


class Tier:
    def __init__(self, name, limit_bytes=None):
        self.name = name
        self.limit = limit_bytes or TIERS[name]
        self.dir = None
        self._peak = 0
        self._stop = threading.Event()
        self._thread = None

    # ---- lifecycle -------------------------------------------------------
    def enter(self):
        """Put THIS process (and so all its future children) under the limit."""
        if not (MEMCG / "memory.limit_in_bytes").exists() or not os.access(MEMCG, os.W_OK):
            raise TierUnavailable("no writable memory cgroup on this machine; cannot enforce a RAM tier")
        self.dir = own_cgroup() / f"neuron-tier-{self.name}-{os.getpid()}"
        self.dir.mkdir()
        (self.dir / "memory.limit_in_bytes").write_text(str(self.limit))
        try:
            (self.dir / "memory.memsw.limit_in_bytes").write_text(str(self.limit))
        except OSError:
            pass
        (self.dir / "cgroup.procs").write_text(str(os.getpid()))
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()
        return self

    def leave(self):
        self._stop.set()
        if self.dir is None:
            return
        try:
            (self.dir.parent / "cgroup.procs").write_text(str(os.getpid()))
            for _ in range(50):
                try:
                    self.dir.rmdir()
                    break
                except OSError:
                    time.sleep(0.1)
        except OSError:
            pass

    def __enter__(self):
        return self.enter()

    def __exit__(self, *exc):
        self.leave()

    # ---- measurement -----------------------------------------------------
    def _stat(self):
        out = {}
        try:
            for line in (self.dir / "memory.stat").read_text().splitlines():
                k, v = line.split()
                out[k] = int(v)
        except (OSError, ValueError, AttributeError):
            pass
        return out

    def used_bytes(self):
        """Memory programs are really holding (not reclaimable file cache), plus swap."""
        s = self._stat()
        return s.get("total_rss", 0) + s.get("total_shmem", 0) + s.get("total_swap", 0)

    def _sample(self):
        while not self._stop.wait(0.25):
            self._peak = max(self._peak, self.used_bytes())

    def peak_bytes(self):
        self._peak = max(self._peak, self.used_bytes())
        return self._peak

    def reset_peak(self):
        self._peak = self.used_bytes()

    def limit_hits(self):
        """How many times the kernel had to push back because the tier was full."""
        try:
            return int((self.dir / "memory.failcnt").read_text())
        except (OSError, ValueError, AttributeError):
            return 0

    def oom_kills(self):
        try:
            for line in (self.dir / "memory.oom_control").read_text().splitlines():
                if line.startswith("oom_kill "):
                    return int(line.split()[1])
        except (OSError, ValueError, AttributeError):
            pass
        return 0
