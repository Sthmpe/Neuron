"""Start NEURON (the brain) so a phone on the same Wi-Fi can use it.

  python3 -m neuron.server                 # uses ~/.neuron/config.json written by the installer
  python3 -m neuron.server code            # a fresh pairing code from the running server (this machine only)
"""
import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

from . import sysinfo


def main(argv=None):
    ap = argparse.ArgumentParser(description="NEURON server")
    ap.add_argument("command", nargs="?", default="start", choices=["start", "code"])
    ap.add_argument("--home", default=os.environ.get("NEURON_HOME", str(Path.home() / ".neuron")))
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--tier", default=None)
    a = ap.parse_args(argv)
    home = Path(a.home)
    cfg = json.loads((home / "config.json").read_text()) if (home / "config.json").exists() else {}
    host, port = a.host or cfg.get("host", "0.0.0.0"), a.port or cfg.get("port", 8642)
    if a.command == "code":
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        print(json.loads(opener.open(f"http://127.0.0.1:{port}/local/pair-code", timeout=5).read())["code"])
        return 0
    if cfg.get("model_dir"):
        os.environ["NEURON_MODEL_DIR"] = cfg["model_dir"]
    if cfg.get("llama_bin") and Path(cfg["llama_bin"]).exists():
        os.environ["NEURON_LLAMA_BIN"] = cfg["llama_bin"]
    (home / "logs").mkdir(parents=True, exist_ok=True)
    from ..agent.capability import default_registry
    from ..brain.models import ModelManager, ModelRunner
    from ..brain.sandbox import Sandbox
    from .app import serve
    tier = a.tier or cfg.get("tier", "4gb")
    mgr = ModelManager()

    def models_status():
        try:
            return {"tier": tier, "builder": mgr.active(tier, "builder")}
        except Exception as e:      # noqa: BLE001
            return {"tier": tier, "problem": str(e)}

    httpd = serve(home, host, port, lambda: ModelRunner(mgr, tier, log_dir=home / "logs"),
                  lambda: Sandbox(timeout=120, mem_mb=1024, toolchains=True), default_registry(), models_status,
                  log=lambda m: print(m, flush=True))
    code = httpd.neuron["pairing"].new_code()
    addrs = sysinfo.lan_addresses() or ["<this computer's address>"]
    print(f"NEURON is running. On your phone (same Wi-Fi) open: " + ", ".join(f"http://{ip}:{port}" for ip in addrs))
    again = f"{home}/start.sh code" if (home / "start.sh").exists() else "python3 -m neuron.server code"
    print(f"Pairing code: {code}  (valid 10 minutes; new code: {again})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.neuron["previews"].close_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
