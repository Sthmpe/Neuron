"""Fault localisation without a model: run every test separately with a line tracer and see which
source lines are run mostly by FAILING tests (the classic 'Ochiai' score). This tells the reviewer
where to look, which matters most for small models."""
import json
import math
import shutil
from pathlib import Path

TRACER = r'''
import json, os, signal, sys, unittest
ROOT = os.getcwd() + os.sep
START, TOP = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)

def flat(suite):
    for t in suite:
        if isinstance(t, unittest.TestSuite):
            yield from flat(t)
        else:
            yield t

def is_test(path):
    rel = path[len(ROOT):]
    name = os.path.basename(rel)
    return name.startswith("test_") or name.endswith("_test.py") or rel.split(os.sep)[0] in ("tests", "test")

class TooSlow(Exception):
    pass

def alarm(*_):
    raise TooSlow()

results = []
suite = unittest.TestLoader().discover(START, top_level_dir=TOP) if TOP else unittest.TestLoader().discover(START)
for test in flat(suite):
    seen = set()
    def tracer(frame, event, arg):
        fn = frame.f_code.co_filename
        if not fn.startswith(ROOT) or is_test(fn):
            return None
        if event == "line":
            seen.add((fn[len(ROOT):], frame.f_lineno))
        return tracer
    result = unittest.TestResult()
    signal.signal(signal.SIGALRM, alarm)
    signal.alarm(8)
    sys.settrace(tracer)
    try:
        test.run(result)
    except TooSlow:
        result.errors.append((test, "timeout"))
    finally:
        sys.settrace(None)
        signal.alarm(0)
    results.append({"test": test.id(), "ok": result.wasSuccessful(), "lines": sorted(seen)})
json.dump(results, open(".neuron_trace.json", "w"))
'''


def suspicious(project, sandbox, work, test_command):
    """Returns {file: {line: score}} or {} when tracing is not possible."""
    if test_command[:4] != ["python3", "-m", "unittest", "discover"]:
        return {}
    args = test_command[4:]
    start = args[args.index("-s") + 1] if "-s" in args else "."
    top = args[args.index("-t") + 1] if "-t" in args else None
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(project, work, ignore=shutil.ignore_patterns(".neuron", ".git", "__pycache__", "*.pyc"))
    (Path(work) / ".neuron_trace.py").write_text(TRACER)
    sandbox.run(["python3", ".neuron_trace.py", start] + ([top] if top else []), work)
    try:
        runs = json.loads((Path(work) / ".neuron_trace.json").read_text())
    except (OSError, ValueError):
        return {}
    failing = [r for r in runs if not r["ok"]]
    if not failing:
        return {}
    in_fail, in_pass = {}, {}
    for r in runs:
        bucket = in_pass if r["ok"] else in_fail
        for f, line in r["lines"]:
            bucket[(f, line)] = bucket.get((f, line), 0) + 1
    out = {}
    for key, nf in in_fail.items():
        score = nf / math.sqrt(len(failing) * (nf + in_pass.get(key, 0)))
        out.setdefault(key[0], {})[key[1]] = round(score, 3)
    return out


def rank_functions(scores, project_map):
    """[(file, qualified name, score)] most suspicious first."""
    ranked = []
    for f, lines in scores.items():
        for fn in (project_map.get(f) or {}).get("functions", []):
            inner = [fn2 for fn2 in project_map[f]["functions"] if fn2["name"].startswith(fn["name"] + ".")]
            own = [s for line, s in lines.items() if fn["line"] < line <= fn["end_line"]
                   and not any(i["line"] <= line <= i["end_line"] for i in inner)]
            if own:
                ranked.append((f, fn["name"], max(own)))
    return sorted(ranked, key=lambda x: -x[2])
