"""Re-check that the locked phase-5 evaluation has not changed since it was locked."""
import hashlib, json, sys
from pathlib import Path
here = Path(__file__).resolve().parent
lock = json.loads((here / "LOCK.json").read_text())
bad = [f for f, h in lock["files"].items() if not (here / f).exists() or hashlib.sha256((here / f).read_bytes()).hexdigest() != h]
print("LOCK INTACT" if not bad else f"CHANGED: {bad}")
sys.exit(1 if bad else 0)
