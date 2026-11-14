"""Network monitor and the simulated network switch used for testing."""
import json
import os
import socket
from pathlib import Path


class NetworkDown(Exception):
    """Raised by an online action when the connection is not there."""


class SimulatedSwitch:
    """A pretend network cable. The state is a small file, so it survives a brain restart
    (the outside world does not reset just because the device rebooted)."""

    def __init__(self, path):
        self.path = Path(path)
        if not self.path.exists():
            self.set(True)

    def set(self, online):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"online": bool(online)}))
        os.replace(tmp, self.path)

    def is_online(self):
        try:
            return bool(json.loads(self.path.read_text())["online"])
        except (OSError, ValueError, KeyError):
            return False


def tcp_probe(host="1.1.1.1", port=53, timeout=2.0):
    """A real connectivity probe for later use on a real device (not used by the demo)."""
    def probe():
        try:
            socket.create_connection((host, port), timeout=timeout).close()
            return True
        except OSError:
            return False
    return probe


class NetworkMonitor:
    """Checks the connection and reports every change (lost / restored)."""

    def __init__(self, probe, on_change=None):
        self.probe = probe
        self.on_change = on_change
        self.last = None

    def check(self):
        online = bool(self.probe())
        if online != self.last:
            previous, self.last = self.last, online
            if self.on_change:
                self.on_change(online, previous)
        return online
