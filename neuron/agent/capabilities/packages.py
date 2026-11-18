"""Upgrading a project's packages safely: isolated copy, the project's own tests, swap in only what passes."""
from ...online import packages
from ..capability import Capability, Outcome, Verdict
from .workspace import detect_test_command


class UpgradePackages(Capability):
    name = "upgrade_packages"
    purpose = "Check pinned packages against PyPI/npm, upgrade in an isolated copy, run the tests, keep only upgrades that pass"
    needs_internet = True
    permissions = ("network", "read_workspace", "write_workspace", "run_code")
    verification = "the project's own tests pass with the new versions in a fresh copy; the real project is rechecked afterwards"
    domains = ("code", "automation")
    fetch = staticmethod(packages.fetch_json)      # replaceable in tests
    installer = staticmethod(packages.install)

    def run(self, job, params):
        ws = job.workspace
        if not packages.pins(ws):
            return Outcome(True, "no pinned packages to check (requirements.txt with == pins, or package.json with exact versions)",
                           {"upgraded": [], "kept_back": []})
        rep = packages.upgrade(ws, job.sandbox, detect_test_command(ws), fetch=self.fetch, effects=job.effects,
                               installer=self.installer, log=job.log)
        notes = packages.memory_notes(rep)
        files = sorted({u.get("file", "requirements.txt") for u in rep["upgraded"]}) if rep["upgraded"] else []
        return Outcome(True, rep["summary"], {**rep, "memory_notes": notes}, files=files)

    def verify(self, job, params, outcome):
        rep = outcome.result
        checks = [{"id": "registry_checked", "pass": not rep.get("errors"),
                   "detail": "; ".join(f"{e['name']}: {e['error']}" for e in rep.get("errors", [])) or "every package checked"}]
        if rep.get("upgraded"):
            cmd = detect_test_command(job.workspace)
            managers = sorted({p["manager"] for p in packages.pins(job.workspace)})
            ok, detail = packages.trial(job.workspace, [], job.sandbox, cmd, managers[0], self.installer)   # the real project as it is now
            checks.append({"id": "tests_pass_after_upgrade", "pass": ok, "detail": detail[-300:]})
            pinned = {p["name"]: p["current"] for p in packages.pins(job.workspace)}
            for u in rep["upgraded"]:
                checks.append({"id": f"{u['name']}_pinned", "pass": pinned.get(u["name"]) == u["to"], "detail": f"{u['name']}=={pinned.get(u['name'])}"})
        return Verdict(all(c["pass"] for c in checks), checks, "the project's tests rerun on a fresh copy of the upgraded project")


CAPABILITIES = [UpgradePackages()]
