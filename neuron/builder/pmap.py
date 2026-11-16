"""Project map: for every source file, its purpose and its interfaces, found by reading the code
(no model involved): functions with their arguments, web routes, database tables."""
import ast
import re
import textwrap
from pathlib import Path

SKIP_DIRS = {".neuron", "kit", "__pycache__", ".git", "node_modules", ".venv", "venv"}
ROUTE = re.compile(r"@\w+\.route\(\s*[\"']([^\"']+)[\"']([^)]*)\)")
TABLE = re.compile(r"CREATE TABLE(?: IF NOT EXISTS)?\s+(\w+)\s*\(([^\"']*?)\)\s*[\"']", re.I | re.S)


def source_files(root):
    root = Path(root)
    return sorted(str(p.relative_to(root)) for p in root.rglob("*.py")
                  if not (set(p.relative_to(root).parts[:-1]) & SKIP_DIRS))


def _functions(tree):
    out = []

    def visit(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = (ast.get_docstring(child) or "").strip().splitlines()
                out.append({"name": prefix + child.name, "args": [a.arg for a in child.args.args],
                            "doc": doc[0] if doc else "", "line": child.lineno, "end_line": child.end_lineno})
                visit(child, prefix + child.name + ".")
            elif isinstance(child, ast.ClassDef):
                visit(child, prefix + child.name + ".")
    visit(tree)
    return out


def describe_file(text):
    info = {"lines": text.count("\n") + 1, "functions": [], "routes": [], "tables": [], "syntax_error": None}
    try:
        tree = ast.parse(text)
        info["functions"] = _functions(tree)
        doc = (ast.get_docstring(tree) or "").strip().splitlines()
        info["doc"] = doc[0] if doc else ""
    except SyntaxError as e:
        info["syntax_error"] = f"{e.msg} (line {e.lineno})"
    for path, rest in ROUTE.findall(text):
        methods = re.findall(r"[\"'](GET|POST)[\"']", rest, re.I) or ["GET"]
        info["routes"].append({"path": path, "methods": [m.upper() for m in methods], "login": "login=True" in rest})
    for name, cols in TABLE.findall(text):
        if not name.startswith("kit_"):
            info["tables"].append({"name": name, "columns": [c.strip().split()[0] for c in cols.split(",") if c.strip()]})
    return info


def build_map(root, purposes=None):
    purposes = purposes or {}
    out = {}
    for rel in source_files(root):
        info = describe_file((Path(root) / rel).read_text(errors="replace"))
        info["purpose"] = purposes.get(rel) or info.get("doc") or ""
        out[rel] = info
    return out


def interfaces_text(m, files=None):
    """A short text listing of interfaces, for a model's context slice."""
    lines = []
    for rel in (files if files is not None else sorted(m)):
        info = m.get(rel)
        if not info:
            continue
        lines.append(f"{rel} - {info.get('purpose', '')}".rstrip(" -"))
        for t in info["tables"]:
            lines.append(f"  table {t['name']}({', '.join(t['columns'])})")
        for r in info["routes"]:
            lines.append(f"  route {'/'.join(r['methods'])} {r['path']}{' (login required)' if r['login'] else ''}")
        for f in info["functions"]:
            if "." not in f["name"] or f["name"].split(".")[-1][:1] != "_":
                lines.append(f"  def {f['name']}({', '.join(f['args'])})" + (f"  # {f['doc']}" if f["doc"] else ""))
    return "\n".join(lines)


def function_source(text, qualname):
    """Source of a function or method, or None."""
    for f in describe_file(text)["functions"]:
        if f["name"] == qualname:
            return "\n".join(text.splitlines()[f["line"] - 1: f["end_line"]])
    return None


def replace_function(text, qualname, new_source):
    """Return `text` with the function replaced by `new_source` (re-indented to fit), or None."""
    for f in describe_file(text)["functions"]:
        if f["name"] == qualname:
            lines = text.splitlines()
            start = f["line"] - 1
            while start > 0 and lines[start - 1].lstrip().startswith("@"):   # keep decorators with the function
                start -= 1
            old_first = lines[f["line"] - 1]
            indent = old_first[: len(old_first) - len(old_first.lstrip())]
            new = textwrap.dedent(new_source).strip("\n").splitlines()
            has_decorator = new and new[0].lstrip().startswith("@")
            keep = [] if has_decorator else lines[start: f["line"] - 1]
            body = [(indent + l if l.strip() else l) for l in new]
            return "\n".join(lines[:start] + keep + body + lines[f["end_line"]:]) + "\n"
    return None
