"""Starts and stops a local llama.cpp server (`llama-server`) and measures its memory."""
import os
import subprocess
import time
from pathlib import Path

from .llm import LlamaClient

_REPO = Path(__file__).resolve().parents[2]
_CANDIDATES = [_REPO.parent / "llama" / "build" / "bin" / "llama-server",
               Path.home() / "llama" / "build" / "bin" / "llama-server"]
DEFAULT_BIN = os.environ.get("NEURON_LLAMA_BIN") or str(next((c for c in _CANDIDATES if c.exists()), _CANDIDATES[0]))
DEFAULT_MODEL_DIR = Path(os.environ.get("NEURON_MODEL_DIR", str(Path(__file__).resolve().parents[2] / "models")))


def find_model():
    """The model file to use: $NEURON_MODEL, or the first .gguf in the models folder (or its store)."""
    if os.environ.get("NEURON_MODEL"):
        return Path(os.environ["NEURON_MODEL"])
    found = sorted(DEFAULT_MODEL_DIR.glob("*.gguf")) or sorted((DEFAULT_MODEL_DIR / "store").glob("*.gguf"))
    return found[0] if found else None


class LlamaServer:
    def __init__(self, model, binary=DEFAULT_BIN, port=8080, ctx=8192, threads=None, log=None, extra_args=()):
        self.model, self.binary, self.port, self.ctx = Path(model), binary, port, ctx
        self.threads = threads or os.cpu_count() or 2
        self.log, self.proc = log, None
        self.extra_args = list(extra_args)      # per-model settings from the model's manifest
        self.url = f"http://127.0.0.1:{port}"

    @staticmethod
    def _port_free(port):
        """Can a server bind this port right now? Tested WITHOUT SO_REUSEADDR, like llama-server: after a crash the
        old server's connections keep the port reserved for about a minute (TIME_WAIT)."""
        import socket
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return True
            except OSError:
                return False

    def _choose_port(self):
        if self._port_free(self.port):
            return
        import socket
        with socket.socket() as s:                 # the usual port is still held: take any free one
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"

    def start(self, wait=600):     # a big model's first load from a cold disk can take several minutes
        if not Path(self.binary).exists():
            raise FileNotFoundError(f"llama-server not found at {self.binary}")
        if not self.model.exists():
            raise FileNotFoundError(f"model file not found: {self.model}")
        if self.log:
            Path(self.log).parent.mkdir(parents=True, exist_ok=True)
        self._choose_port()
        out = open(self.log, "ab") if self.log else subprocess.DEVNULL
        self.proc = subprocess.Popen(
            [self.binary, "-m", str(self.model), "--host", "127.0.0.1", "--port", str(self.port),
             "-c", str(self.ctx), "-t", str(self.threads), "-np", "1", "--no-webui",
             # load-mode none: read the model into memory once. With the default (mmap) this CPU's
             # AMX code path keeps a second, repacked copy: 2.7 GB resident instead of 1.7 GB.
             # cache-ram 0: no growing prompt cache, so memory stays bounded.
             "--load-mode", "none", "--cache-ram", "0"] + self.extra_args,
            stdout=out, stderr=subprocess.STDOUT)
        client = LlamaClient(self.url)
        end = time.time() + wait
        while time.time() < end:
            if self.proc.poll() is not None:
                raise RuntimeError(f"llama-server exited with code {self.proc.returncode}")
            if client.healthy():
                return client
            time.sleep(0.3)
        self.stop()
        raise RuntimeError("llama-server did not become ready in time")

    def _status(self, key):
        try:
            for line in open(f"/proc/{self.proc.pid}/status"):
                if line.startswith(key + ":"):
                    return int(line.split()[1]) * 1024
        except (OSError, AttributeError, ValueError):
            pass
        return 0

    def rss_bytes(self):
        return self._status("VmRSS")

    def peak_rss_bytes(self):
        return self._status("VmHWM")

    def reset_peak(self):
        """Reset the kernel's peak-memory counter for the server process."""
        try:
            with open(f"/proc/{self.proc.pid}/clear_refs", "w") as f:
                f.write("5")
            return True
        except (OSError, AttributeError):
            return False

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
