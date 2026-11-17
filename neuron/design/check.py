"""Run the designer checks on a running app; turn fixable findings into token changes (fix.py logic here)."""
import json
import os
import subprocess
from pathlib import Path

from . import color as C

SCRIPT = Path(__file__).resolve().parent / "check.js"
TOKEN_FIXABLE = {"contrast", "crowding", "hierarchy", "overflow"}


def run(url, paths=("/",), login=None, shots=None, timeout=300):
    env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    arg = json.dumps({"url": url, "paths": list(paths), "login": login, "shots": str(shots) if shots else None})
    try:
        p = subprocess.run(["node", str(SCRIPT), arg], capture_output=True, text=True, timeout=timeout, env=env)
        return json.loads(p.stdout.strip().splitlines()[-1])["findings"]
    except (subprocess.TimeoutExpired, ValueError, IndexError) as e:
        return [{"rule": "checker_error", "severity": "fail", "width": "-", "path": "-", "detail": type(e).__name__}]


def summary(findings):
    fails = [f for f in findings if f["severity"] == "fail"]
    by = {}
    for f in fails:
        by[f["rule"]] = by.get(f["rule"], 0) + 1
    return {"fails": len(fails), "warnings": len(findings) - len(fails), "by_rule": by}


def fix(design, findings):
    """Change tokens (never the content or the code) to answer what the checks found. Returns a list of
    plain-English changes; an empty list means nothing token-fixable was found."""
    t, changes = design["tokens"], []
    rules = {f["rule"] for f in findings if f["severity"] == "fail"}
    if "contrast" in rules:
        for key in ("color-ink-muted", "color-ink-soft", "color-link", "color-accent-ink", "color-support-ink", "color-on-strong-muted"):
            if key in t:
                bg = t["color-strong"] if key == "color-on-strong-muted" else t["color-surface-3"]
                new = C.ensure_contrast(t[key], bg, 5.2 if key != "color-ink-soft" else 4.6)
                if new != t[key]:
                    t[key] = new
                    changes.append(f"made {key[6:]} text darker for contrast")
        if not changes:
            changes.append("contrast problem found that tokens cannot fix (reported)")
    if "crowding" in rules:
        t["space"] = f"{round(float(t['space'][:-2]) * 1.15, 2)}px"
        changes.append("gave everything 15% more space")
    if "hierarchy" in rules:
        t["ratio"] = str(round(min(1.42, float(t["ratio"]) + 0.05), 3))
        changes.append("made the type scale steeper so headings stand out")
    if "overflow" in rules:
        t["ratio"] = str(round(max(1.15, float(t["ratio"]) - 0.05), 3))
        changes.append("made the largest headings a little smaller so they fit narrow screens")
    return changes
