"""Tool registry: where the brain discovers what it can do."""
import importlib
import importlib.util
import os
import pkgutil
from pathlib import Path

from .base import Tool


class UnknownTool(KeyError):
    pass


class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, tool):
        if isinstance(tool, type):
            tool = tool()
        if not isinstance(tool, Tool) or not tool.name:
            raise TypeError("a tool must be a Tool with a name")
        self._tools[tool.name] = tool
        return tool

    def get(self, name):
        try:
            return self._tools[name]
        except KeyError:
            raise UnknownTool(f"no tool named '{name}' is registered") from None

    def has(self, name):
        return name in self._tools

    def names(self):
        return sorted(self._tools)

    def specs(self, planner_only=True):
        return [t.spec() for _, t in sorted(self._tools.items()) if t.planner_visible or not planner_only]

    def _take(self, module):
        for tool in getattr(module, "TOOLS", []):
            self.register(tool)

    def discover(self, extra_dirs=None):
        """Load every tool module shipped in neuron.brain.tools, then any plug-in folders.

        A plug-in is a .py file that defines `TOOLS = [MyTool(), ...]`. Folders come from
        `extra_dirs` and the NEURON_TOOLS_DIR environment variable."""
        package = importlib.import_module(__package__)
        for info in pkgutil.iter_modules(package.__path__):
            if info.name not in ("base", "registry"):
                self._take(importlib.import_module(f"{__package__}.{info.name}"))
        dirs = list(extra_dirs or []) + [d for d in os.environ.get("NEURON_TOOLS_DIR", "").split(os.pathsep) if d]
        for d in dirs:
            for path in sorted(Path(d).glob("*.py")):
                spec = importlib.util.spec_from_file_location(f"neuron_plugin_{path.stem}", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self._take(module)
        return self


def default_registry(extra_dirs=None):
    return ToolRegistry().discover(extra_dirs)
