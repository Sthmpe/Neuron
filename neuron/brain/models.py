"""Model manager: models are swappable files. Nothing in the code names a model.

  manifest (a small JSON file)  +  model file (.gguf)   ->  install
  activate a model for a tier (and role)                 ->  swap
  go back to what was active before                      ->  rollback

A model that does not fit a tier's memory is refused. "Fits" means: the memory the model
server needs (measured if available, otherwise estimated from the file size) plus a fixed
reserve for the rest of NEURON must be at most the tier's total RAM.

Command line:
  python3 -m neuron.brain.models list
  python3 -m neuron.brain.models install <manifest.json> [--file path/to/model.gguf]
  python3 -m neuron.brain.models measure <model-id>
  python3 -m neuron.brain.models activate <tier> <model-id> [--role planner|reviewer|builder|all]
  python3 -m neuron.brain.models rollback <tier>
  python3 -m neuron.brain.models remove <model-id>
"""
import argparse
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from .tiers import TIERS

ROLES = ("planner", "reviewer", "builder")
RESERVE_BYTES = 400 * 1024 ** 2        # brain + sandbox + dev server, kept free next to the model
EST_OVERHEAD_BYTES = 320 * 1024 ** 2   # context + working buffers, used until a model is measured
DEFAULT_ROOT = Path(os.environ.get("NEURON_MODEL_DIR", str(Path(__file__).resolve().parents[2] / "models")))


class ModelError(Exception):
    pass


class ModelDoesNotFit(ModelError):
    pass


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class ModelManager:
    def __init__(self, root=DEFAULT_ROOT, tiers=None):
        self.root = Path(root)
        self.store = self.root / "store"
        self.state_file = self.root / "state.json"
        self.tiers = dict(tiers or TIERS)
        self.store.mkdir(parents=True, exist_ok=True)
        self.state = json.loads(self.state_file.read_text()) if self.state_file.exists() else \
            {"installed": {}, "active": {}, "history": {}}

    def _save(self):
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=1))
        os.replace(tmp, self.state_file)

    # ---- install / remove ------------------------------------------------
    def install(self, manifest, file=None, verify=True):
        """Register a model. `manifest` is a dict or a path to a JSON file."""
        if not isinstance(manifest, dict):
            manifest = json.loads(Path(manifest).read_text())
        for key in ("id", "file"):
            if not manifest.get(key):
                raise ModelError(f"manifest is missing '{key}'")
        dest = self.store / manifest["file"]
        if file and Path(file).resolve() != dest.resolve():
            shutil.copyfile(file, dest)
        if not dest.exists():
            raise ModelError(f"model file not found: {dest}")
        if verify and manifest.get("sha256"):
            got = sha256_file(dest)
            if got != manifest["sha256"]:
                raise ModelError(f"checksum mismatch for {manifest['file']}: file is damaged or not the stated model")
        entry = dict(manifest)
        entry.update(size_bytes=dest.stat().st_size, installed_at=time.time(),
                     measured_rss_bytes=(self.state["installed"].get(manifest["id"]) or {}).get("measured_rss_bytes"))
        self.state["installed"][manifest["id"]] = entry
        self._save()
        return entry

    def remove(self, model_id):
        self.get(model_id)
        users = [f"{t}/{r}" for t, roles in self.state["active"].items() for r, m in roles.items() if m == model_id]
        if users:
            raise ModelError(f"{model_id} is active for {', '.join(users)}; activate another model or roll back first")
        del self.state["installed"][model_id]
        self._save()

    def get(self, model_id):
        try:
            return self.state["installed"][model_id]
        except KeyError:
            raise ModelError(f"model '{model_id}' is not installed") from None

    def path(self, model_id):
        return self.store / self.get(model_id)["file"]

    def list(self):
        return sorted(self.state["installed"].values(), key=lambda m: m["size_bytes"])

    # ---- memory fit ------------------------------------------------------
    def needed_bytes(self, model_id):
        m = self.get(model_id)
        return m.get("measured_rss_bytes") or int(m["size_bytes"] + EST_OVERHEAD_BYTES)

    def fits(self, model_id, tier):
        return self.needed_bytes(model_id) + RESERVE_BYTES <= self.tiers[tier]

    def record_measurement(self, model_id, rss_bytes):
        self.get(model_id)["measured_rss_bytes"] = int(rss_bytes)
        self._save()

    # ---- activate / rollback --------------------------------------------
    def activate(self, tier, model_id, role="all"):
        if tier not in self.tiers:
            raise ModelError(f"unknown tier '{tier}'")
        if not self.fits(model_id, tier):
            mb = lambda b: round(b / 2 ** 20)
            raise ModelDoesNotFit(
                f"{model_id} needs about {mb(self.needed_bytes(model_id))} MB plus {mb(RESERVE_BYTES)} MB for the "
                f"rest of the system; the {tier} tier has {mb(self.tiers[tier])} MB. Refused.")
        current = dict(self.state["active"].get(tier) or {})
        new = dict(current)
        for r in (ROLES if role == "all" else (role,)):
            if r not in ROLES:
                raise ModelError(f"unknown role '{r}'")
            new[r] = model_id
        if new != current:
            self.state["history"].setdefault(tier, []).append(current)
            self.state["active"][tier] = new
            self._save()
        return new

    def rollback(self, tier):
        history = self.state["history"].get(tier) or []
        if not history:
            raise ModelError(f"nothing to roll back for tier '{tier}'")
        self.state["active"][tier] = history.pop()
        self._save()
        return self.state["active"][tier]

    def active(self, tier, role):
        model_id = (self.state["active"].get(tier) or {}).get(role)
        if not model_id:
            raise ModelError(f"no model is active for tier '{tier}', role '{role}'")
        return model_id


class ModelRunner:
    """Keeps at most ONE model in memory. Asking for a role whose model differs from the
    loaded one stops the old server and starts the new one."""

    def __init__(self, manager, tier, port=18080, log_dir=None, threads=None, overrides=None):
        self.manager, self.tier, self.port = manager, tier, port
        self.log_dir, self.threads = log_dir, threads
        self.overrides = overrides or {}      # role -> model id, to try a model without activating it
        self.server = self.client_obj = self.loaded = None
        self.loads, self.load_seconds = 0, 0.0

    def model_for(self, role):
        return self.overrides.get(role) or self.manager.active(self.tier, role)

    def client(self, role):
        from .llama_server import LlamaServer
        model_id = self.model_for(role)
        if self.loaded != model_id:
            self.unload()
            m = self.manager.get(model_id)
            log = Path(self.log_dir) / f"llama-{model_id}.log" if self.log_dir else None
            self.server = LlamaServer(self.manager.path(model_id), port=self.port, ctx=m.get("context_tokens", 8192),
                                      threads=self.threads, log=log, extra_args=m.get("server_args") or [])
            t0 = time.time()
            self.client_obj = self.server.start()
            self.client_obj.extra_body = dict(m.get("request_extra") or {})
            self.client_obj._model = model_id
            self.loads += 1
            self.load_seconds += time.time() - t0
            self.loaded = model_id
        return self.client_obj

    def unload(self):
        if self.server:
            self.server.stop()
        self.server = self.client_obj = self.loaded = None


def measure(manager, model_id, port=18099):
    """Load the model for real, generate a little, and record the memory the server uses."""
    from .llama_server import LlamaServer
    m = manager.get(model_id)
    server = LlamaServer(manager.path(model_id), port=port, ctx=m.get("context_tokens", 8192),
                         extra_args=m.get("server_args") or [])
    t0 = time.time()
    client = server.start()
    load = time.time() - t0
    try:
        client.extra_body = dict(m.get("request_extra") or {})
        reply = client.chat([{"role": "user", "content": "Write a Python function that returns the larger of two "
                              "numbers, then explain it in one sentence."}], max_tokens=120)
        rss = server.peak_rss_bytes()
    finally:
        server.stop()
    manager.record_measurement(model_id, rss)
    return {"model": model_id, "rss_mb": round(rss / 2 ** 20), "load_seconds": round(load, 1),
            "tokens_per_second": round(reply.tokens_per_second, 1), "sample": reply.text[:200]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="NEURON model manager")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    p = sub.add_parser("install"); p.add_argument("manifest"); p.add_argument("--file")
    p = sub.add_parser("measure"); p.add_argument("model")
    p = sub.add_parser("activate"); p.add_argument("tier"); p.add_argument("model"); p.add_argument("--role", default="all")
    p = sub.add_parser("rollback"); p.add_argument("tier")
    p = sub.add_parser("remove"); p.add_argument("model")
    a = ap.parse_args(argv)
    mgr = ModelManager()
    try:
        if a.cmd == "list":
            for m in mgr.list():
                fits = " ".join(t for t in mgr.tiers if mgr.fits(m["id"], t)) or "none"
                how = "measured" if m.get("measured_rss_bytes") else "estimated"
                print(f"{m['id']:<26} {m['size_bytes'] / 2**30:5.2f} GB file  needs {mgr.needed_bytes(m['id']) / 2**20:6.0f} MB ({how})  fits: {fits}")
            for tier, roles in sorted(mgr.state["active"].items()):
                print(f"active {tier}: " + ", ".join(f"{r}={m}" for r, m in sorted(roles.items())))
        elif a.cmd == "install":
            print("installed", mgr.install(a.manifest, a.file)["id"])
        elif a.cmd == "measure":
            print(json.dumps(measure(mgr, a.model), indent=1))
        elif a.cmd == "activate":
            print(mgr.activate(a.tier, a.model, a.role))
        elif a.cmd == "rollback":
            print(mgr.rollback(a.tier))
        elif a.cmd == "remove":
            mgr.remove(a.model); print("removed", a.model)
    except ModelError as e:
        raise SystemExit(f"REFUSED: {e}")


if __name__ == "__main__":
    main()
