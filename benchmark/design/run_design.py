"""Proof of design taste: 20 varied requests, each built into a real page by the real builder and model.

    NEURON_DESIGN=1 python3 -m benchmark.design.run_design --tier 2gb [--model ID] [--only a,b]

For each request (network off, inside the tier's memory limit):
  * the builder plans, builds and tests the page, then runs its design review (FULL condition)
  * independent checks on the finished page: the designer checks (contrast, sideways scrolling, tap
    targets, hierarchy, one main action, no border lines, crowding, overlap, em dashes)
  * colour fidelity: every colour the owner named must appear in the design, hue kept within 8 degrees
  * screenshots at phone (390 px) and desktop (1280 px) width, committed for review
Results: benchmark/design/results.json and results.md; screenshots in benchmark/design/screens/.
"""
import argparse
import json
import os
import shutil
import sys
import time
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmark.run_benchmark import cut_network                   # noqa: E402
from neuron.brain.models import ModelManager, ModelRunner         # noqa: E402
from neuron.brain.sandbox import Sandbox                          # noqa: E402
from neuron.brain.tiers import Tier                               # noqa: E402
from neuron.builder.build import TrialRun, build_full             # noqa: E402
from neuron.builder.design_step import login_for, paths_for       # noqa: E402
from neuron.design import check                                   # noqa: E402
from neuron.design import color as C                              # noqa: E402

OUT = ROOT / "benchmark" / "design"
SHOTJS = ROOT / "neuron" / "design" / "shoot_jpeg.js"


def shoot(url, prefix, paths, login):
    import subprocess
    env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    arg = json.dumps({"url": url, "out": str(prefix), "paths": paths, "login": login})
    subprocess.run(["node", str(SHOTJS), arg], capture_output=True, text=True, env=env, timeout=300)


def colour_fidelity(design):
    asked = design["palette"].get("user_colours") or []
    tokens = [v for k, v in design["tokens"].items() if k.startswith("color-") and isinstance(v, str) and v.startswith("#")]
    roles = list(design["palette"]["roles"].values())
    out = []
    for c in asked:
        L, Ch, H = C.hex_to_oklch(c["hex"])
        if Ch < 0.03:     # black, white, grey: judged by lightness, not hue
            ok = any(abs(C.hex_to_oklch(t)[0] - L) < 0.12 and C.hex_to_oklch(t)[1] < 0.04 for t in tokens + roles)
        else:
            ok = any(C.hex_to_oklch(t)[1] > 0.02 and C.hue_distance(C.hex_to_oklch(t)[2], H) <= 8 for t in tokens)
        out.append({"word": c["word"], "hex": c["hex"], "kept": ok})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="2gb")
    ap.add_argument("--model")
    ap.add_argument("--only")
    a = ap.parse_args()
    if os.environ.get("NEURON_DESIGN", "1") == "0":
        sys.exit("the design system is switched off (NEURON_DESIGN=0)")
    manager = ModelManager()
    model = a.model or manager.active(a.tier, "builder")
    requests = json.loads((OUT / "requests.json").read_text())
    only = set(a.only.split(",")) if a.only else None
    res_file = OUT / "results.json"
    results = json.loads(res_file.read_text()) if res_file.exists() else {"rows": []}
    done = {r["name"] for r in results["rows"]}
    net = cut_network()
    if net["internet_reachable"]:
        sys.exit("network could not be cut off")
    tier = Tier(a.tier).enter()
    sandbox = Sandbox(timeout=60, mem_mb=256)
    runner = ModelRunner(manager, a.tier, overrides={r: model for r in ("planner", "reviewer", "builder")}, log_dir=OUT / "run")
    work = ROOT / "benchmark" / "run" / "design"
    work.mkdir(parents=True, exist_ok=True)
    results.update(tier=a.tier, model=model, network=net["method"])
    try:
        for req in requests:
            name = req["name"]
            if name in done or (only and name not in only):
                continue
            project = work / name
            shutil.rmtree(project, ignore_errors=True)
            tier.reset_peak()
            t0 = time.time()
            summary = build_full(project, req["request"], runner, sandbox, log=lambda m: print(f"  {name}: {m}", flush=True),
                                 max_seconds=30 * 60, design=True)
            runner.unload()
            row = {"name": name, "built": summary.get("ok"), "build_seconds": round(time.time() - t0, 1),
                   "peak_mb": round(tier.peak_bytes() / 2 ** 20), "builder_error": summary.get("error", "")[:300]}
            theme = project / "theme.json"
            if theme.exists():
                d = json.loads(theme.read_text())
                spec = json.loads((project / ".neuron" / "spec.json").read_text())["spec"]
                row.update(mood=d["mood"], palette=d["palette"]["name"], colour_source=d["palette"]["source"],
                           fonts=d["fonts"], variants=d["variants"], fingerprint=d["fingerprint"], reason=d["reason"],
                           colours=colour_fidelity(d), review=summary.get("design"))
                trial = TrialRun(project, sandbox, work / (name + "__shot"))
                url = trial.start()
                if url:
                    findings = check.run(url, paths_for(spec), login_for(spec), design=d)
                    row["checks"] = check.summary(findings)
                    row["failed_checks"] = [f for f in findings if f["severity"] == "fail"][:15]
                    (OUT / "screens").mkdir(parents=True, exist_ok=True)
                    shoot(url, OUT / "screens" / name, paths_for(spec)[1:] if spec.get("kind") == "app" else ["/"], login_for(spec))
                    trial.stop()
                else:
                    row["checks"] = {"fails": None, "note": "the app did not start for the final check"}
                shutil.rmtree(work / (name + "__shot"), ignore_errors=True)
            results["rows"].append(row)
            res_file.write_text(json.dumps(results, indent=1))
            print(f"{name}: built={row['built']} checks={row.get('checks')} colours={row.get('colours')} {row['build_seconds']}s", flush=True)
    finally:
        runner.unload()
        tier.leave()
    rows = results["rows"]
    fps = [r["fingerprint"] for r in rows if r.get("fingerprint")]
    overlaps = [sum(x == y for x, y in zip(p, q)) for p, q in combinations(fps, 2)]
    results["variety"] = {"designs": len(fps), "max_shared_choices_of_8": max(overlaps) if overlaps else None,
                          "mean_shared_choices_of_8": round(sum(overlaps) / len(overlaps), 2) if overlaps else None,
                          "distinct_palettes": len({r.get("palette") for r in rows}), "distinct_heroes": len({(r.get("variants") or {}).get("hero") for r in rows})}
    res_file.write_text(json.dumps(results, indent=1))
    write_md(results)


def write_md(results):
    rows = results["rows"]
    lines = ["# Design taste proof: 20 requests", "",
             f"Model: `{results.get('model')}` at the {results.get('tier')} tier, network off ({results.get('network')}).", "",
             "| Request | Built | Mood | Palette | Hero / features / form | Design checks failed | Colours asked: kept? | Phone | Desktop |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        v = r.get("variants") or {}
        cols = ", ".join(f"{c['word']}: {'yes' if c['kept'] else 'NO'}" for c in r.get("colours") or []) or "none asked"
        chk = (r.get("checks") or {}).get("fails")
        img = "screens/" + r["name"] + ("-home" if not r["name"].endswith("_app") else "-" + "")
        lines.append(f"| {r['name']} | {'yes' if r['built'] else 'NO'} | {r.get('mood', '-')} | {r.get('palette', '-')} | "
                     f"{v.get('hero', '-')} / {v.get('features', '-')} / {v.get('form', '-')} | {chk} | {cols} | "
                     f"[phone](screens/{r['name']}-home-phone.jpg) | [desktop](screens/{r['name']}-home-desktop.jpg) |")
    var = results.get("variety") or {}
    lines += ["", f"Variety: {var.get('designs')} designs; any two share at most {var.get('max_shared_choices_of_8')} of 8 main choices "
              f"(average {var.get('mean_shared_choices_of_8')}); {var.get('distinct_palettes')} different palettes, "
              f"{var.get('distinct_heroes')} different hero layouts."]
    (OUT / "results.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
