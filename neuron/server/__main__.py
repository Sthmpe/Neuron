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
    ap.add_argument("--https", action="store_true", default=None, help="encrypt phone traffic with a certificate made on this computer")
    a = ap.parse_args(argv)
    home = Path(a.home)
    cfg = json.loads((home / "config.json").read_text()) if (home / "config.json").exists() else {}
    host, port = a.host or cfg.get("host", "0.0.0.0"), a.port or cfg.get("port", 8642)
    if a.command == "code":
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        import ssl
        cert = home / "tls" / "cert.pem"
        tries = [("http", opener)]
        if cert.exists():                                 # the server may be running with --https: try that first
            ctx = ssl.create_default_context(cafile=str(cert))
            ctx.check_hostname = False                    # we talk to 127.0.0.1; the certificate itself is still checked
            tries.insert(0, ("https", urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ctx))))
        for scheme, op in tries:
            try:
                print(json.loads(op.open(f"{scheme}://127.0.0.1:{port}/local/pair-code", timeout=5).read())["code"])
                return 0
            except OSError:
                continue
        print("NEURON is not running on this computer (start it with ~/.neuron/start.sh)")
        return 1
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
            return {"tier": tier, "builder": mgr.active(tier, "builder"), "online_boost": boost.status()}
        except Exception as e:      # noqa: BLE001
            return {"tier": tier, "problem": str(e)}

    from ..online.boost import BoostedRunner, OnlineBoost
    boost = OnlineBoost.from_home(home, online_check=sysinfo.online, log=lambda m: print(m, flush=True))

    def make_runner():
        local = ModelRunner(mgr, tier, log_dir=home / "logs")
        return BoostedRunner(local, boost) if boost.configured() else local

    tls_ctx, fp = None, None
    if a.https or cfg.get("https"):
        from . import tls
        cert, key = tls.ensure_cert(home)
        tls_ctx, fp = tls.context(cert, key), tls.fingerprint(cert)
    httpd = serve(home, host, port, make_runner,
                  lambda: Sandbox(timeout=120, mem_mb=1024, toolchains=True), default_registry(), models_status,
                  log=lambda m: print(m, flush=True), tls=tls_ctx)
    code = httpd.neuron["pairing"].new_code()
    # NEURON_PUBLIC_HOST: the address the phone should use when this runs inside WSL behind port forwarding
    addrs = [os.environ["NEURON_PUBLIC_HOST"]] if os.environ.get("NEURON_PUBLIC_HOST") else (sysinfo.lan_addresses() or ["<this computer's address>"])
    scheme = "https" if tls_ctx else "http"
    print(f"NEURON is running. On your phone (same Wi-Fi) open: " + ", ".join(f"{scheme}://{ip}:{port}" for ip in addrs))
    if fp:
        print("The phone will warn that it does not know this certificate. Continue only if the certificate's SHA-256\n"
              f"fingerprint it shows is: {fp}")
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
