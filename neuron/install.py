"""Install NEURON on this computer.

  python3 -m neuron.install                 # detect memory, pick the frozen model for that tier, fetch, check, self-test
  python3 -m neuron.install --plan          # only show what would happen

Steps, each reported in plain words:
  1. measure the computer's memory and keep room for the operating system
  2. pick the largest memory tier that fits, and the model frozen for that tier
  3. download the model (resumes after a cut), then check its SHA-256 against the frozen value
  4. self-test: load the model and get an answer, run code in the sandbox, list tools that are missing
  5. write the settings file the server reads (config.json)
Nothing is marked as working unless it was actually run here.
"""
import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FROZEN = REPO / "model_manifests" / "frozen.json"
GIB = 1024 ** 3
TIER_BYTES = {"2gb": 2 * GIB, "4gb": 4 * GIB, "8gb": 8 * GIB}


class InstallError(Exception):
    pass


def memory_bytes(meminfo="/proc/meminfo"):
    vals = {}
    for line in open(meminfo):
        k, v = line.split(":", 1)
        vals[k] = int(v.split()[0]) * 1024
    return vals["MemTotal"], vals.get("MemAvailable", vals["MemTotal"])


def os_reserve(total):
    """Memory left for the operating system, desktop and anything else the owner runs."""
    return max(GIB, int(total * 0.15))


def choose_tier(total, tiers):
    usable = total - os_reserve(total)
    fitting = [t for t in tiers if TIER_BYTES[t] <= usable]
    if not fitting:
        raise InstallError(f"this computer has {total / GIB:.1f} GB of memory; after keeping {os_reserve(total) / GIB:.1f} GB for the "
                           f"system, {usable / GIB:.1f} GB is left, and the smallest NEURON tier needs 2 GB. "
                           "Use --tier 2gb to try anyway (it may run out of memory).")
    best = max(fitting, key=lambda t: TIER_BYTES[t])
    return best, usable


def windows_plan(ram_gb, build, wsl_version=""):
    """The decisions scripts/install-windows.ps1 makes (keep both the same). Windows keeps max(3 GB, 30%) of memory;
    WSL gets the rest as its limit; inside WSL the usual rule (keep max(1 GB, 15%) for Ubuntu) picks the tier.
    Mirrored networking needs Windows 11 22H2 (build 22621) and WSL 2.0 or newer; otherwise port forwarding."""
    if build < 19041:
        return {"ok": False, "why": "WSL2 needs Windows 10 version 2004 (build 19041) or newer"}
    reserve = max(3, math.ceil(ram_gb * 0.30))
    wsl_gb = math.floor(ram_gb - reserve)
    if wsl_gb < 3:
        return {"ok": False, "why": f"after keeping {reserve} GB for Windows, less than 3 GB is left for NEURON", "reserve_gb": reserve}
    usable = wsl_gb - max(1, wsl_gb * 0.15)
    tier = "8gb" if usable >= 8 else "4gb" if usable >= 4 else "2gb"
    major = int(wsl_version.split(".")[0]) if wsl_version and wsl_version.split(".")[0].isdigit() else 0
    return {"ok": True, "reserve_gb": reserve, "wsl_memory_gb": wsl_gb, "tier": tier,
            "networking": "mirrored" if build >= 22621 and major >= 2 else "port forwarding"}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url, dest, sha256, log=print, tries=8, wait=20):
    """Fetch url to dest, resuming a partial file; refuse a file whose checksum is wrong."""
    dest = Path(dest)
    part = dest.with_name(dest.name + ".part")
    last = None
    for attempt in range(1, tries + 1):
        have = part.stat().st_size if part.exists() else 0
        req = urllib.request.Request(url, headers={"User-Agent": "neuron-installer", **({"Range": f"bytes={have}-"} if have else {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                if have and r.status != 206:          # server ignored the resume request: start again
                    have = 0
                total = have + int(r.headers.get("Content-Length") or 0)
                with open(part, "ab" if have else "wb") as f:
                    done, shown = have, time.time()
                    for chunk in iter(lambda: r.read(1 << 20), b""):
                        f.write(chunk)
                        done += len(chunk)
                        if time.time() - shown > 15 and total:
                            log(f"  {done / 2 ** 20:,.0f} of {total / 2 ** 20:,.0f} MB")
                            shown = time.time()
            if total and done < total:                 # connection dropped without an error: resume
                raise OSError(f"connection closed after {done} of {total} bytes")
            break
        except urllib.error.HTTPError as e:
            if e.code == 416 and part.exists():        # already complete
                break
            last = e
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            last = e
        log(f"  download try {attempt} failed ({last}); waiting {wait}s and resuming")
        time.sleep(wait)
    else:
        raise InstallError(f"could not download {url}: {last}")
    got = sha256_file(part)
    if got != sha256:
        part.unlink()
        raise InstallError(f"checksum mismatch for {dest.name}: expected {sha256}, got {got}. The file was deleted; nothing was installed.")
    os.replace(part, dest)
    return got


def self_test_model(mgr, model_id, port=18097, log=print):
    from .brain.llama_server import LlamaServer
    m = mgr.get(model_id)
    server = LlamaServer(mgr.path(model_id), port=port, ctx=m.get("context_tokens", 8192), extra_args=m.get("server_args") or [])
    t0 = time.time()
    client = server.start()
    load = time.time() - t0
    try:
        client.extra_body = dict(m.get("request_extra") or {})
        reply = client.chat([{"role": "user", "content": "What is 17 plus 25? Reply with the number only."}], max_tokens=40)
        speed = client.chat([{"role": "user", "content": "List the numbers from 1 to 60 in words, separated by commas."}],
                            max_tokens=100)                # long enough to measure writing speed
        rss = server.peak_rss_bytes()
    finally:
        server.stop()
    mgr.record_measurement(model_id, rss)
    ok = "42" in reply.text
    return {"passed": ok, "answer": reply.text.strip()[:80], "load_seconds": round(load, 1), "memory_mb": round(rss / 2 ** 20),
            "tokens_per_second": round(speed.completion_tokens / max(speed.seconds, 0.01), 1)}


def self_test_sandbox():
    from .brain.sandbox import Sandbox
    sb = Sandbox(timeout=30, mem_mb=256)
    if not sb.available():
        return {"passed": False, "detail": "bubblewrap is not installed, so NEURON will refuse to run code"}
    with tempfile.TemporaryDirectory() as d:
        r = sb.run(["python3", "-c", "print(6 * 7)"], d)
    return {"passed": r.exit_code == 0 and r.output.strip() == "42", "detail": r.output.strip()[:80] or f"exit {r.exit_code}"}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Install NEURON on this computer")
    ap.add_argument("--home", default=os.environ.get("NEURON_HOME", str(Path.home() / ".neuron")))
    ap.add_argument("--model-dir", default=None, help="where model files live (default: <home>/models)")
    ap.add_argument("--llama-bin", default=None, help="path of llama-server (default: <home>/llama/build/bin/llama-server)")
    ap.add_argument("--tier", choices=sorted(TIER_BYTES), help="override the memory tier")
    ap.add_argument("--frozen", default=str(FROZEN))
    ap.add_argument("--port", type=int, default=8642)
    ap.add_argument("--plan", action="store_true", help="show what would happen and stop")
    ap.add_argument("--skip-model-test", action="store_true")
    a = ap.parse_args(argv)
    home = Path(a.home).expanduser()
    model_dir = Path(a.model_dir or home / "models").expanduser()
    llama_bin = Path(a.llama_bin or home / "llama" / "build" / "bin" / "llama-server").expanduser()
    say = lambda m: print(m, flush=True)

    if not Path(a.frozen).exists():
        raise InstallError(f"no frozen model list at {a.frozen}; the models for each tier have not been frozen yet")
    frozen = json.loads(Path(a.frozen).read_text())
    total, avail = memory_bytes()
    if a.tier:
        tier, usable = a.tier, total - os_reserve(total)
        say(f"1. Memory: {total / GIB:.1f} GB in total. Tier {tier} chosen by you.")
    else:
        tier, usable = choose_tier(total, list(frozen["tiers"]))
        say(f"1. Memory: {total / GIB:.1f} GB in total, {os_reserve(total) / GIB:.1f} GB kept for the system, "
            f"{usable / GIB:.1f} GB for NEURON.")
    model = frozen["tiers"][tier]
    say(f"2. Tier {tier}: model {model['id']} ({model['bytes'] / GIB:.2f} GB file, measured {model.get('measured_rss_mb', '?')} MB in memory, "
        f"licence {model.get('licence', '?')}).")
    dest = model_dir / "store" / model["file"]
    if a.plan:
        say(f"3. Would download {model['source']}\n   to {dest}\n   and check SHA-256 {model['sha256']}")
        return 0

    model_dir.joinpath("store").mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(model_dir).free
    if dest.exists():
        say(f"3. Model file already here; checking its SHA-256")
        if sha256_file(dest) != model["sha256"]:
            raise InstallError(f"{dest} does not match the frozen checksum; delete it and run the installer again")
    else:
        if free < model["bytes"] * 1.05:
            raise InstallError(f"not enough disk space: the model needs {model['bytes'] / GIB:.1f} GB, {free / GIB:.1f} GB is free")
        say(f"3. Downloading {model['file']} ({model['bytes'] / GIB:.2f} GB)")
        download(model["source"], dest, model["sha256"], log=say)
    say("   checksum matches the frozen value")

    os.environ["NEURON_MODEL_DIR"] = str(model_dir)
    if llama_bin.exists():
        os.environ["NEURON_LLAMA_BIN"] = str(llama_bin)
    from .brain.models import ModelManager
    mgr = ModelManager(model_dir)
    manifest = {k: model[k] for k in ("id", "file", "sha256", "source", "licence", "context_tokens", "server_args", "request_extra") if k in model}
    mgr.install(manifest, verify=False)            # verified just above
    mgr.activate(tier, model["id"])

    results = {}
    if a.skip_model_test:
        say("4. Model self-test skipped (asked to)")
    else:
        if not llama_bin.exists():
            raise InstallError(f"llama-server not found at {llama_bin}; run scripts/install.sh, which builds it")
        say("4. Self-test: loading the model and asking a question")
        results["model"] = self_test_model(mgr, model["id"], log=say)
        r = results["model"]
        say(f"   {'passed' if r['passed'] else 'FAILED'}: answered {r['answer']!r} in memory {r['memory_mb']} MB, "
            f"writes about {r['tokens_per_second']} tokens per second, loaded in {r['load_seconds']} s")
    results["sandbox"] = self_test_sandbox()
    say(f"   sandbox {'passed' if results['sandbox']['passed'] else 'FAILED'}: {results['sandbox']['detail']}")
    from .agent.capability import default_registry
    missing = [c for c in default_registry().report() if not c["available"]]
    results["missing_tools"] = [{"name": c["name"], "missing": c.get("missing")} for c in missing]
    for c in missing:
        say(f"   not available: {c['name']} (needs {', '.join(c.get('missing') or [])})")
    if not missing:
        say("   every built-in tool has what it needs")

    home.mkdir(parents=True, exist_ok=True)
    cfg = {"tier": tier, "model": model["id"], "model_dir": str(model_dir), "llama_bin": str(llama_bin), "host": "0.0.0.0", "port": a.port,
           "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"), "memory_total_mb": round(total / 2 ** 20), "self_test": results}
    (home / "config.json").write_text(json.dumps(cfg, indent=1))
    say(f"5. Settings written to {home / 'config.json'}")
    failed = [k for k in ("model", "sandbox") if k in results and not results[k]["passed"]]
    if failed:
        say("Install finished with problems: " + ", ".join(failed) + " self-test failed. See above.")
        return 2
    say("Install finished. Start NEURON with: python3 -m neuron.server")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except InstallError as e:
        print("Install stopped: " + str(e), file=sys.stderr)
        sys.exit(1)
