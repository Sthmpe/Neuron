"""Starts and stops a local llama.cpp server (`llama-server`) and measures its memory."""
import os
import subprocess
import time
from pathlib import Path

from .llm import LlamaClient

DEFAULT_BIN = os.environ.get("NEURON_LLAMA_BIN", str(Path.home() / "llama" / "build" / "bin" / "llama-server"))
DEFAULT_MODEL_DIR = Path(os.environ.get("NEURON_MODEL_DIR", str(Path(__file__).resolve().parents[2] / "models")))


def find_model():
    """The model file to use: $NEURON_MODEL, or the first .gguf in the models folder."""
    if os.environ.get("NEURON_MODEL"):
        return Path(os.environ["NEURON_MODEL"])
    found = sorted(DEFAULT_MODEL_DIR.glob("*.gguf"))
    return found[0] if found else None


class LlamaServer:
    def __init__(self, model, binary=DEFAULT_BIN, port=8080, ctx=8192, threads=None, log=None):
        self.model, self.binary, self.port, self.ctx = Path(model), binary, port, ctx
        self.threads = threads or os.cpu_count() or 2
        self.log, self.proc = log, None
        self.url = f"http://127.0.0.1:{port}"

    def start(self, wait=180):
        if not Path(self.binary).exists():
            raise FileNotFoundError(f"llama-server not found at {self.binary}")
        if not self.model.exists():
            raise FileNotFoundError(f"model file not found: {self.model}")
        out = open(self.log, "ab") if self.log else subprocess.DEVNULL
        self.proc = subprocess.Popen(
            [self.binary, "-m", str(self.model), "--host", "127.0.0.1", "--port", str(self.port),
             "-c", str(self.ctx), "-t", str(self.threads), "-np", "1", "--no-webui"],
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
