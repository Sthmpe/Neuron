"""Re-check that the locked core-proof task set and examiners have not changed since they were locked.

  python3 benchmark/proof/verify_lock.py            (prints LOCK INTACT or the changed files)
  python3 benchmark/proof/verify_lock.py --write    (only when locking, or for a numbered amendment in LOCKED.md)
"""
import hashlib
import json
import sys
import time
from pathlib import Path

here = Path(__file__).resolve().parent
LOCKED = ["__init__.py", "app_exam.js", "defs_apps.py", "defs_bugs.py", "defs_docs.py", "defs_features.py",
          "examine.py", "make_tasks.py", "validate.py", "validation.json"]


def files():
    out = list(LOCKED)
    out += sorted(str(p.relative_to(here)) for p in (here / "tasks").rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    return out


def digest(rel):
    return hashlib.sha256((here / rel).read_bytes()).hexdigest()


if "--write" in sys.argv:
    hashes = {f: digest(f) for f in files()}
    whole = hashlib.sha256("".join(f + h for f, h in hashes.items()).encode()).hexdigest()
    (here / "LOCK.json").write_text(json.dumps({"locked_at": time.strftime("%Y-%m-%d %H:%M"), "whole": whole, "files": hashes}, indent=1))
    print("LOCK WRITTEN", whole)
    sys.exit(0)
lock = json.loads((here / "LOCK.json").read_text())
bad = [f for f, h in lock["files"].items() if not (here / f).exists() or digest(f) != h]
bad += [f"(new) {f}" for f in files() if f not in lock["files"]]
print("LOCK INTACT" if not bad else f"CHANGED: {bad}")
sys.exit(1 if bad else 0)
