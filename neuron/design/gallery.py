"""Render one content set in many forced variant combinations, for visual review of the kit itself."""
import copy
import json
import os
import subprocess
from pathlib import Path

from neuron.brain.sandbox import Sandbox
from neuron.design.preview import make_project

SHOT = Path(__file__).resolve().parent / "shoot.js"


def shoot(url, out_prefix, paths=("/",), widths=((1280, 800, "desktop"), (390, 844, "phone"))):
    env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    arg = json.dumps({"url": url, "out": str(out_prefix), "paths": list(paths), "widths": [list(w) for w in widths]})
    return subprocess.run(["node", str(SHOT), arg], capture_output=True, text=True, env=env, timeout=300)


def render(folder, spec, design, files, out_prefix, paths=("/",), sandbox=None, before=None):
    proj = make_project(folder, spec, design, files)
    srv = (sandbox or Sandbox(mem_mb=256)).start(["python3", "app.py"], proj)
    try:
        if not srv.wait_ready("/static/theme.css"):
            return None, srv.output()
        if before:
            before(srv.url)
        r = shoot(srv.url, out_prefix, paths)
        return r, ""
    finally:
        srv.stop()
