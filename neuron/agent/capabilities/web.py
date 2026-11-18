"""Websites and web apps, through the step-3 builder (spec -> small tasks -> browser-checked) with the design system."""
from ...builder.build import build_full
from ..capability import Capability, Outcome, Verdict


class BuildWebApp(Capability):
    name = "build_web_app"
    purpose = "Plan, build and test a website or record-keeping web app (pages, forms, lists, search, login, dashboard)"
    permissions = ("write_workspace", "run_code", "use_model")
    resources = {"ram_mb": 300, "uses_model": True}
    verification = "acceptance checks over HTTP on the running app, then the designer checks in a real browser"
    domains = ("web",)

    def run(self, job, params):
        from ...brain.sandbox import Sandbox
        r = build_full(job.workspace / "app", job.state.goal()["request"], job.runner, Sandbox(timeout=60, mem_mb=256),
                       log=lambda m: job.log("    " + m), design=job.design)
        tasks = r.get("tasks", {})
        llm = r.get("llm") or {}
        job.count(llm.get("calls", 0), llm.get("tokens", 0), llm.get("seconds", 0.0))   # the builder calls the model itself
        mb = r.get("made_by") or {}
        parts = [f"{k} ({mb[k]} file{'s' if mb[k] != 1 else ''})" for k in ("model", "template", "code") if mb.get(k)]
        made = " + ".join(parts) or "model"
        return Outcome(bool(r.get("ok")), f"app {'passes' if r.get('ok') else 'fails'} its acceptance checks; tasks {tasks}",
                       {"builder": r}, ["app/"], made_by=made)

    def verify(self, job, params, outcome):
        r = outcome.result["builder"]
        checks = [{"id": "acceptance_checks", "pass": bool(r.get("ok")), "detail": r.get("error", "")[:400]}]
        if r.get("design") is not None:
            checks.append({"id": "design_checks", "pass": r["design"].get("fails") == 0, "detail": str(r["design"].get("by_rule"))})
        return Verdict(all(c["pass"] for c in checks), checks, "HTTP acceptance checks + browser design checks")


CAPABILITIES = [BuildWebApp()]
