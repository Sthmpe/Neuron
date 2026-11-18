"""Keeping a project's packages current without ever breaking it.

When online, for a project with pinned packages (requirements.txt for Python, package.json for Node):
  1. ask the official registry (PyPI, npm) for each package's newest stable release and its documentation and
     release-notes links;
  2. build an isolated copy of the project with the CURRENT versions and run its tests (the baseline: if the project's
     own tests already fail, nothing is upgraded, because a failure afterwards would prove nothing);
  3. build another isolated copy with ALL the new versions and run the tests; if they pass, the new pins are swapped
     into the real project, after a backup;
  4. if they fail, try each package alone in a fresh copy, keep the ones whose tests pass, and test those together;
  5. anything that fails is rolled back simply by throwing its copy away: the real project is only written once,
     after the tests passed, and rollback() restores the backup if the owner wants the old versions back.
Packages are installed from wheels only (no package's own setup code runs during installation) and the tests run in
the sandbox without network.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.\-]*(?:\[[\w,\-]+\])?)\s*==\s*([0-9][\w.]*)\s*(;[^#]*)?(#.*)?$")
NPM_PIN = re.compile(r"^([\^~]?)(\d+\.\d+\.\d+)$")
REGISTRY = {"pip": "https://pypi.org/pypi/{name}/json", "npm": "https://registry.npmjs.org/{name}/latest"}


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "NEURON-local-assistant/0.1 (package update check)",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def version_tuple(v):
    """(1, 26, 4) from '1.26.4'; None for pre-releases (rc, beta, dev), which are never offered as upgrades."""
    if re.search(r"(a|b|rc|dev|alpha|beta|pre|-)\d*", v.split("+")[0].lower().replace(".post", "")):
        return None
    parts = [int(x) for x in re.findall(r"\d+", v.split("+")[0])]
    return tuple(parts) if parts else None


# ---- what is pinned ---------------------------------------------------------------------------------------------
def pins(project):
    project, out = Path(project), []
    req = project / "requirements.txt"
    if req.exists():
        for i, line in enumerate(req.read_text().splitlines()):
            m = PIN.match(line.strip())
            if m:
                out.append({"manager": "pip", "file": "requirements.txt", "name": m.group(1), "current": m.group(2), "line": i})
    pkg = project / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text())
        except ValueError:
            data = {}
        for section in ("dependencies", "devDependencies"):
            for name, spec in (data.get(section) or {}).items():
                m = NPM_PIN.match(str(spec))
                if m:
                    out.append({"manager": "npm", "file": "package.json", "name": name, "current": m.group(2),
                                "prefix": m.group(1), "section": section})
    return out


def latest(pin, fetch=fetch_json):
    """Newest stable release and its documentation links, from the official registry."""
    name = pin["name"].split("[")[0]
    data = fetch(REGISTRY[pin["manager"]].format(name=name))
    if pin["manager"] == "pip":
        info = data.get("info") or {}
        urls = info.get("project_urls") or {}
        docs = {k: v for k, v in urls.items() if re.search(r"doc|change|release|history|news|home|source", k, re.I)}
        if info.get("home_page"):
            docs.setdefault("Homepage", info["home_page"])
        files = (data.get("releases") or {}).get(info.get("version", ""), [])
        released = min((f.get("upload_time", "")[:10] for f in files), default="")
        return {"version": info.get("version", ""), "docs": docs, "released": released,
                "requires_python": info.get("requires_python") or ""}
    repo = data.get("repository")
    docs = {"Homepage": data.get("homepage", "")}
    if isinstance(repo, dict) and repo.get("url"):
        docs["Source"] = repo["url"]
    return {"version": data.get("version", ""), "docs": {k: v for k, v in docs.items() if v}, "released": "", "requires_python": ""}


def python_ok(requires):
    """Whether this computer's Python satisfies a package's 'requires_python' (only >= and < bounds are checked)."""
    here = sys.version_info[:2]
    for op, v in re.findall(r"(>=|<=|<|>|==|!=)\s*(\d+(?:\.\d+)?)", requires or ""):
        t = tuple(int(x) for x in v.split("."))[:2]
        if (op == ">=" and here < t) or (op == "<" and here >= t) or (op == ">" and here <= t) or (op == "<=" and here > t):
            return False
    return True


def outdated(project, fetch=fetch_json):
    """Pinned packages with a newer stable release: [{name, current, latest, docs, released, ...}]."""
    out = []
    for p in pins(project):
        try:
            info = latest(p, fetch)
        except Exception as e:                  # noqa: BLE001  one unreachable package never stops the others
            out.append({**p, "latest": None, "error": f"{type(e).__name__}: {e}"[:200]})
            continue
        new, cur = version_tuple(info["version"]), version_tuple(p["current"])
        if new and cur and new > cur and python_ok(info["requires_python"]):
            out.append({**p, "latest": info["version"], "docs": info["docs"], "released": info["released"]})
    return out


# ---- isolated copies --------------------------------------------------------------------------------------------
def write_pins(folder, items):
    """Write the given versions into the manifest files of a folder (a copy, or the real project after the tests)."""
    folder = Path(folder)
    by_file = {}
    for it in items:
        by_file.setdefault(it["file"], []).append(it)
    for fname, its in by_file.items():
        f = folder / fname
        if fname == "requirements.txt":
            lines = f.read_text().splitlines()
            for it in its:
                m = PIN.match(lines[it["line"]].strip())
                if m and m.group(1) == it["name"]:
                    lines[it["line"]] = f"{it['name']}=={it['latest']}" + (f" {m.group(3).strip()}" if m.group(3) else "") \
                        + (f"  {m.group(4)}" if m.group(4) else "")
            f.write_text("\n".join(lines) + "\n")
        else:
            data = json.loads(f.read_text())
            for it in its:
                data[it["section"]][it["name"]] = it.get("prefix", "") + it["latest"]
            f.write_text(json.dumps(data, indent=2) + "\n")


def _copy(project):
    work = Path(tempfile.mkdtemp(prefix="neuron-upgrade-"))
    dst = work / "project"
    shutil.copytree(project, dst, ignore=shutil.ignore_patterns(".neuron", ".git", "__pycache__", ".venv", "node_modules"))
    return dst


def install(folder, manager, timeout=600):
    """Install the folder's pinned packages inside the folder only. Returns (ok, detail). Needs the internet."""
    folder = Path(folder)
    if manager == "pip":
        steps = [[sys.executable, "-m", "venv", "--system-site-packages", str(folder / ".venv")],
                 [str(folder / ".venv" / "bin" / "python"), "-m", "pip", "install", "-q", "--disable-pip-version-check",
                  "--only-binary=:all:", "-r", str(folder / "requirements.txt")]]
    else:
        steps = [["npm", "install", "--no-audit", "--no-fund", "--ignore-scripts", "--loglevel=error"]]
    for cmd in steps:
        try:
            r = subprocess.run(cmd, cwd=folder, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            return False, f"{' '.join(cmd[:3])}: {e}"
        if r.returncode != 0:
            return False, (r.stderr or r.stdout)[-800:]
    return True, "installed"


def run_tests(folder, sandbox, test_cmd, manager):
    """The project's own tests in the sandbox (no network), using the copy's own packages. Returns (ok, output tail)."""
    cmd = list(test_cmd)
    if manager == "pip" and cmd and cmd[0] in ("python3", "python"):
        cmd[0] = "/workspace/.venv/bin/python"
    res = sandbox.run(cmd, folder, timeout=600)
    from ..brain.tools.fix_code import tests_passed
    ok = tests_passed(res, cmd[1:3] == ["-m", "unittest"]) if manager == "pip" else res.ok
    return ok, res.output[-1500:]


def trial(project, items, sandbox, test_cmd, manager, installer=install, tester=run_tests):
    """Install `items` (new versions; [] for the baseline) in a fresh copy and run the tests. The copy is always removed."""
    copy = _copy(project)
    try:
        if items:
            write_pins(copy, items)
        ok, detail = installer(copy, manager)
        if not ok:
            return False, "install failed: " + detail
        return tester(copy, sandbox, test_cmd, manager)
    finally:
        shutil.rmtree(copy.parent, ignore_errors=True)


# ---- the whole upgrade ------------------------------------------------------------------------------------------
def backup(project, files):
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = Path(project) / ".neuron" / "upgrades" / stamp
    dest.mkdir(parents=True, exist_ok=True)
    for f in files:
        if (Path(project) / f).exists():
            shutil.copy(Path(project) / f, dest / f)
    return dest


def rollback(project):
    """Put back the package versions from before the last upgrade. Returns the backup used, or None."""
    root = Path(project) / ".neuron" / "upgrades"
    backups = sorted(p for p in root.glob("*") if p.is_dir()) if root.exists() else []
    if not backups:
        return None
    last = backups[-1]
    for f in last.iterdir():
        shutil.copy(f, Path(project) / f.name)
    shutil.move(str(last), str(root / ("rolled-back-" + last.name)))
    return last


def upgrade(project, sandbox, test_cmd, fetch=fetch_json, effects=None, installer=install, tester=run_tests, log=print):
    """Check, upgrade in isolation, test, and swap in only what passed. Returns a plain report (also saved in .neuron)."""
    project = Path(project)
    report = {"checked": time.strftime("%Y-%m-%d %H:%M"), "outdated": [], "upgraded": [], "kept_back": [], "baseline": None}
    found = outdated(project, fetch)
    items = [o for o in found if o.get("latest")]
    report["outdated"] = [{k: o[k] for k in ("manager", "name", "current", "latest", "docs", "released")} for o in items]
    report["errors"] = [{"name": o["name"], "error": o["error"]} for o in found if o.get("error")]
    if not items:
        report["summary"] = "every pinned package is already the newest stable release"
        return _save(project, report)
    if not test_cmd:
        report["summary"] = "newer versions exist, but the project has no tests, so nothing was upgraded (it could not be proved safe)"
        report["kept_back"] = [{"name": o["name"], "why": "no tests to prove the upgrade safe"} for o in items]
        return _save(project, report)
    for manager in sorted({o["manager"] for o in items}):
        group = [o for o in items if o["manager"] == manager]
        ok, detail = trial(project, [], sandbox, test_cmd, manager, installer, tester)
        report["baseline"] = {"passed": ok, "detail": detail[-300:]}
        if not ok:
            report["kept_back"] += [{"name": o["name"], "why": "the project's tests fail even with the current versions"} for o in group]
            continue
        ok, detail = trial(project, group, sandbox, test_cmd, manager, installer, tester)
        good = group if ok else []
        if not ok:
            log(f"  all {manager} upgrades together fail the tests; trying each package alone")
            for o in group:
                ok1, d1 = trial(project, [o], sandbox, test_cmd, manager, installer, tester)
                if ok1:
                    good.append(o)
                else:
                    report["kept_back"].append({"name": o["name"], "from": o["current"], "to": o["latest"], "why": "tests fail: " + d1[-300:]})
            if len(good) > 1:
                ok, detail = trial(project, good, sandbox, test_cmd, manager, installer, tester)
                if not ok:              # each passes alone but not together: keep only the first, the safe choice
                    report["kept_back"] += [{"name": o["name"], "why": "passes alone but not with the others"} for o in good[1:]]
                    good = good[:1]
        if good:
            files = sorted({o["file"] for o in good}) + (["package-lock.json"] if manager == "npm" else [])
            new_text = json.dumps([(o["name"], o["latest"]) for o in good])
            key = f"upgrade:{project.name}:{manager}:{hashlib.sha1(new_text.encode()).hexdigest()[:12]}"

            def swap():
                b = backup(project, files)
                write_pins(project, good)
                if manager == "npm" and (project / "package-lock.json").exists():     # keep the lock file in step
                    subprocess.run(["npm", "install", "--package-lock-only", "--ignore-scripts", "--no-audit", "--no-fund",
                                    "--loglevel=error"], cwd=project, capture_output=True, timeout=600)
                return {"backup": str(b.relative_to(project))}

            res = effects.once(key, f"swap in {len(good)} upgraded {manager} package(s)", swap, repeat_safe=True) if effects else swap()
            report["upgraded"] += [{"name": o["name"], "from": o["current"], "to": o["latest"], "docs": o.get("docs", {}),
                                    "backup": (res or {}).get("backup")} for o in good]
    up, kept = len(report["upgraded"]), len(report["kept_back"])
    report["summary"] = f"{up} package(s) upgraded after the tests passed, {kept} kept at their current version"
    return _save(project, report)


def _save(project, report):
    p = Path(project) / ".neuron" / "upgrades.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    history = []
    try:
        history = json.loads(p.read_text())
    except (OSError, ValueError):
        pass
    p.write_text(json.dumps(history + [report], indent=1))
    return report


def memory_notes(report, source_date=None):
    """What an upgrade check learned, as memory notes: each package's newest release and its docs (rechecked later)."""
    date = source_date or time.strftime("%Y-%m-%d")
    notes = []
    for o in report.get("outdated", []):
        docs = ", ".join(f"{k}: {v}" for k, v in list((o.get("docs") or {}).items())[:2])
        notes.append({"kind": "fact", "text": f"{o['name']} {o['latest']} is the newest stable release on "
                                              f"{'PyPI' if o['manager'] == 'pip' else 'npm'} (checked {date}). {docs}".strip(),
                      "source": REGISTRY[o["manager"]].format(name=o["name"].split("[")[0]), "version": o["latest"],
                      "verified": True, "tags": ("package", o["manager"], o["name"])})
    return notes
