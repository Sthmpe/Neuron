"""Design inside the builder: choose once, save with the reason, keep it on resume, review and fix it.

  choose_and_save : at plan time. The design (mood, palette, fonts, variants, tokens) and its plain-English
                    reason go to <project>/theme.json (read by the kit) and .neuron/design.json (project state),
                    so a resumed build, a different model or a new session keeps exactly the same look.
  review          : after the app passes its acceptance checks. The app is rendered in a real browser at
                    phone, tablet and desktop width; what a designer would notice is turned into token
                    changes and checked again (at most `rounds` times). Content and code are never changed here.
"""
import json
import shutil
import time
from pathlib import Path

from ..design import check, engine


def paths_for(spec):
    if spec.get("kind") == "app":
        pages = ["/login", "/"] if spec.get("dashboard") else ["/login"]
        return pages + [f"/{e['name']}" for e in spec.get("entities", [])]
    return ["/"]


def login_for(spec):
    return [spec["username"], spec["password"]] if spec.get("kind") == "app" and spec.get("login_required") else None


def choose_and_save(project, request, spec, state=None, seed=None):
    project = Path(project)
    existing = project / "theme.json"
    if existing.exists():                      # resume: the look was decided before and is kept
        return json.loads(existing.read_text())
    design = engine.choose(request, app_name=spec.get("app_name", ""), kind=spec.get("kind", "site"), seed=seed)
    existing.write_text(json.dumps(design, indent=1))
    if state is not None:
        (state.dir / "design.json").write_text(json.dumps({"choice": design, "review": []}, indent=1))
        state.decide("design", "choice", design["reason"])
    return design


def review(project, spec, sandbox, state=None, rounds=2, shots_dir=None, log=print):
    """Returns {"rounds": [...], "final": summary}. Never raises: a design problem is reported, not hidden."""
    from .build import TrialRun
    project = Path(project)
    theme_file = project / "theme.json"
    design = json.loads(theme_file.read_text())
    scratch = project.parent / (project.name + "__design")
    history = []
    for n in range(1, rounds + 2):
        trial = TrialRun(project, sandbox, scratch)
        url = trial.start()
        if not url:
            history.append({"round": n, "error": "the app did not start", "log": trial.log[-500:]})
            break
        try:
            shots = (Path(shots_dir) / f"r{n}") if shots_dir else None
            if shots:
                shots.parent.mkdir(parents=True, exist_ok=True)
            findings = check.run(url, paths_for(spec), login_for(spec), shots=shots, design=design)
        finally:
            trial.stop()
        summ = check.summary(findings)
        entry = {"round": n, "summary": summ, "findings": findings[:40], "at": time.time()}
        if summ["fails"] == 0 or n == rounds + 1:
            history.append(entry)
            break
        changes = check.fix(design, findings)
        entry["changes"] = changes
        history.append(entry)
        log(f"  design review round {n}: {summ['by_rule']} -> {changes}")
        if not changes or all("cannot fix" in c for c in changes):
            break
        theme_file.write_text(json.dumps(design, indent=1))
    shutil.rmtree(scratch, ignore_errors=True)
    final = history[-1].get("summary") if history else None
    if state is not None:
        f = state.dir / "design.json"
        rec = json.loads(f.read_text()) if f.exists() else {"choice": design, "review": []}
        rec["choice"], rec["review"] = design, history
        f.write_text(json.dumps(rec, indent=1))
        state.decide("design", "review", f"design review: {final}")
    return {"rounds": history, "final": final}
