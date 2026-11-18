"""Machine status for the phone: memory, load, connectivity, models."""
import os
import socket
import time


def memory():
    info = {}
    try:
        for line in open("/proc/meminfo"):
            k, v = line.split(":")
            info[k] = int(v.split()[0]) * 1024
    except OSError:
        return {}
    return {"total_mb": info.get("MemTotal", 0) >> 20, "available_mb": info.get("MemAvailable", 0) >> 20}


def load():
    try:
        return {"load_1min": round(os.getloadavg()[0], 2), "cpus": os.cpu_count()}
    except OSError:
        return {}


_net = {"at": 0, "online": None}


def online(cache_seconds=30):
    """True if the internet answers. Checked rarely, never blocks for long."""
    if time.time() - _net["at"] < cache_seconds:
        return _net["online"]
    ok = False
    for host in ("1.1.1.1", "8.8.8.8"):
        try:
            socket.create_connection((host, 53), timeout=1.5).close()
            ok = True
            break
        except OSError:
            pass
    if not ok and any(os.environ.get(v) for v in ("HTTPS_PROXY", "https_proxy")):
        # behind a web proxy (offices, some cloud machines) direct connections fail although the internet works
        import urllib.request
        try:
            req = urllib.request.Request("https://pypi.org/simple/", method="HEAD", headers={"User-Agent": "NEURON-local-assistant/0.1"})
            with urllib.request.urlopen(req, timeout=4):
                ok = True
        except Exception:                    # noqa: BLE001  any failure means: not online
            ok = False
    _net.update(at=time.time(), online=ok)
    return ok


def lan_addresses():
    out = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        out.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(a for a in out if not a.startswith("127."))
