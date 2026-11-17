"""Capabilities: the one interface every skill plugs into, and the registry that discovers them."""
import importlib
import importlib.util
import os
import pkgutil
import shutil
from dataclasses import dataclass, field
from pathlib import Path

PERMISSIONS = {"read_workspace", "write_workspace", "run_code", "network", "send_message", "use_model"}


@dataclass
class Outcome:
    """What a capability did. `files` are workspace-relative paths it produced or changed."""
    ok: bool
    summary: str
    result: dict = field(default_factory=dict)
    files: list = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    made_by: str = "deterministic"          # deterministic | model | template | model+template


@dataclass
class Verdict:
    """An independent check of an outcome. `checks` = [{"id", "pass", "detail"}]."""
    passed: bool
    checks: list = field(default_factory=list)
    how: str = ""
    rework: str = None        # id of an earlier task that must be redone (with these failures as feedback)

    @property
    def failures(self):
        return [c for c in self.checks if not c["pass"]]


class Missing(Exception):
    """A required compiler, application, library or model is not installed."""


class Capability:
    name = ""
    purpose = ""
    inputs = {}                 # {"path": {"type": "path", "required": True, "description": ...}}
    outputs = []                # plain descriptions of what it produces
    needs_internet = False
    permissions = ("read_workspace",)
    resources = {"ram_mb": 50, "uses_model": False}
    verification = ""           # how its output is checked, in plain words
    requires = {"binaries": [], "modules": []}
    domains = ()                # code, web, documents, data, research, media, automation
    planner_visible = True

    # ---- availability -------------------------------------------------------------------------
    def missing(self):
        out = [b for b in self.requires.get("binaries", []) if shutil.which(b) is None]
        for m in self.requires.get("modules", []):
            if importlib.util.find_spec(m) is None:
                out.append(f"python module {m}")
        return out

    def available(self):
        return not self.missing()

    def spec(self):
        return {"name": self.name, "purpose": self.purpose, "inputs": self.inputs, "outputs": self.outputs,
                "needs_internet": self.needs_internet, "permissions": list(self.permissions), "resources": self.resources,
                "verification": self.verification, "available": self.available(), "missing": self.missing()}

    def check_inputs(self, params):
        problems = []
        for k, rule in self.inputs.items():
            if rule.get("required") and (k not in params or params[k] in (None, "")):
                problems.append(f"missing input '{k}'")
        return problems

    # ---- work ---------------------------------------------------------------------------------
    def run(self, job, params) -> Outcome:
        raise NotImplementedError

    def verify(self, job, params, outcome) -> Verdict:
        """Default: nothing independent to check beyond the outcome itself; say so honestly."""
        return Verdict(outcome.ok, [{"id": "ran", "pass": outcome.ok, "detail": outcome.summary}], "no independent check")


class Registry:
    def __init__(self):
        self.caps = {}

    def add(self, cap):
        if isinstance(cap, type):
            cap = cap()
        self.caps[cap.name] = cap
        return cap

    def get(self, name):
        if name not in self.caps:
            raise KeyError(f"no capability named '{name}'")
        return self.caps[name]

    def has(self, name):
        return name in self.caps

    def catalogue(self, domain=None, available_only=True):
        """Short lines for a model's context: name, purpose, inputs. Small on purpose."""
        lines = []
        for c in sorted(self.caps.values(), key=lambda c: c.name):
            if not c.planner_visible or (available_only and not c.available()) or (domain and domain not in c.domains):
                continue
            ins = ", ".join(f"{k}{'' if v.get('required') else '?'}" for k, v in c.inputs.items())
            lines.append(f"- {c.name}({ins}): {c.purpose}")
        return "\n".join(lines)

    def report(self):
        return [c.spec() for c in sorted(self.caps.values(), key=lambda c: c.name)]

    def discover(self, extra_dirs=()):
        pkg = importlib.import_module(__package__ + ".capabilities")
        for info in pkgutil.iter_modules(pkg.__path__):
            mod = importlib.import_module(f"{pkg.__name__}.{info.name}")
            for cap in getattr(mod, "CAPABILITIES", []):
                self.add(cap)
        for d in list(extra_dirs) + [x for x in os.environ.get("NEURON_CAPABILITIES_DIR", "").split(os.pathsep) if x]:
            for path in sorted(Path(d).glob("*.py")):
                spec = importlib.util.spec_from_file_location(f"neuron_cap_{path.stem}", path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                for cap in getattr(mod, "CAPABILITIES", []):
                    self.add(cap)
        return self


def default_registry(extra_dirs=()):
    return Registry().discover(extra_dirs)
