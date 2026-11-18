"""Websites and web apps, through the step-3 builder (spec -> small tasks -> browser-checked) with the design system."""
from pathlib import Path

from ...builder.build import build_full
from ..capability import Capability, Outcome, Verdict


def zip_app(workspace):
    """app.zip: the whole app in one download (without NEURON's own records, caches or the database)."""
    import zipfile
    app = Path(workspace) / "app"
    with zipfile.ZipFile(Path(workspace) / "app.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(app.rglob("*")):
            rel = f.relative_to(app)
            if f.is_file() and rel.parts[0] != ".neuron" and "__pycache__" not in rel.parts and not rel.name.startswith("data.db"):
                z.write(f, Path("app") / rel)


class BuildWebApp(Capability):
    name = "build_web_app"
    purpose = "Plan, build and test a website or record-keeping web app (pages, forms, lists, search, login, dashboard)"
    permissions = ("write_workspace", "run_code", "use_model")
    resources = {"ram_mb": 300, "uses_model": True}
    verification = "acceptance checks over HTTP on the running app, then the designer checks in a real browser"
    domains = ("web",)

    def run(self, job, params):
        from ...brain.sandbox import Sandbox
        from ...media.images import PHOTO_EXT
        photos = sorted(p for p in (job.workspace / "inputs").glob("*") if p.suffix.lower() in PHOTO_EXT) \
            if (job.workspace / "inputs").exists() else []                  # the owner's own photos come first
        r = build_full(job.workspace / "app", job.state.goal()["request"], job.runner, Sandbox(timeout=60, mem_mb=256),
                       log=lambda m: job.log("    " + m), design=job.design, photos=photos)
        tasks = r.get("tasks", {})
        llm = r.get("llm") or {}
        job.count(llm.get("calls", 0), llm.get("tokens", 0), llm.get("seconds", 0.0))   # the builder calls the model itself
        mb = r.get("made_by") or {}
        parts = [f"{k} ({mb[k]} file{'s' if mb[k] != 1 else ''})" for k in ("model", "template", "code") if mb.get(k)]
        made = " + ".join(parts) or "model"
        gaps = r.get("not_built") or []
        names = {"schema": "database", "dashboard": "dashboard", "home": "home page"}
        parts = ", ".join(f"{names.get(k, k.replace('_', ' ') + ' page')} ({v.get('made_by') or v.get('status')})" for k, v in tasks.items())
        files = ["app/"]
        if r.get("ok"):                                    # one download for the whole app, for the phone
            zip_app(job.workspace)
            files.append("app.zip")
        from ...media.images import Manifest
        pics = Manifest(job.workspace / "app")
        result = {"builder": r}
        if pics.needed():                         # placeholders shown: licensed photos are fetched when online
            result["add_tasks"] = [{"id": "images", "capability": "find_images", "title": "Find licensed photos for the site",
                                    "params": {"project": "app"}}]
        out = Outcome(bool(r.get("ok")), f"the app {'passes' if r.get('ok') else 'fails'} its checks; parts: {parts}"
                      + (f"; NOT built (asked for, not supported yet): {', '.join(gaps)}" if gaps else "")
                      + (f"; images needed: {len(pics.needed())} placeholder(s) until photos are added" if pics.needed() else ""),
                      result, files, made_by=made)
        return out

    def verify(self, job, params, outcome):
        r = outcome.result["builder"]
        checks = [{"id": "acceptance_checks", "pass": bool(r.get("ok")), "detail": r.get("error", "")[:400]}]
        gaps = r.get("not_built") or []
        checks.append({"id": "every_requested_feature_built", "pass": not gaps, "gap": True,
                       "detail": ("asked for but not supported yet: " + "; ".join(gaps)) if gaps else ""})
        problems = r.get("content_problems") or []
        if r.get("content_notes") or problems:
            checks.append({"id": "words_checked", "pass": not problems, "gap": True,
                           "detail": ("the words need a person's edit: " + "; ".join(problems[:4])) if problems else
                                     "; ".join(r.get("content_notes", [])[:4])})
        if r.get("design") is not None:
            by_rule = r["design"].get("by_rule") or {}
            checks.append({"id": "design_checks", "pass": r["design"].get("fails") == 0,
                           "detail": "no problems found" if not by_rule else ", ".join(f"{k}: {v}" for k, v in by_rule.items())})
        return Verdict(all(c["pass"] for c in checks), checks, "HTTP acceptance checks + browser design checks")


CAPABILITIES = [BuildWebApp()]
