"""Context slices: only what one step needs, within a budget. The job's memory is the disk, not the prompt."""
import re
from pathlib import Path

SKIP = {".neuron", "kit", "__pycache__", ".git", "node_modules", ".venv", "venv", ".cache", ".gopath", ".cargo"}
CODE_EXT = {".py", ".cpp", ".cc", ".h", ".hpp", ".c", ".go", ".rs", ".java", ".js", ".ts", ".dart", ".kt", ".swift"}


def files(workspace, exts=None):
    ws = Path(workspace)
    out = []
    for p in sorted(ws.rglob("*")):
        rel = p.relative_to(ws)
        if p.is_file() and not (set(rel.parts) & SKIP) and (exts is None or p.suffix in exts):
            out.append(str(rel))
    return out


def clip(text, n):
    return text if len(text) <= n else text[: n // 2] + "\n[...]\n" + text[-n // 2:]


def slice_for(job, task, extra="", budget=6000):
    """Goal, criteria, this task, what earlier tasks produced (summaries only), the last failure."""
    g = job.state.goal()
    parts = [f"Goal (owner's words): {clip(g.get('request', ''), 1500)}"]
    if g.get("criteria"):
        parts.append("Done when: " + "; ".join(c["text"] for c in g["criteria"][:8]))
    plan = job.state.plan()
    done = [t for t in plan if t["status"] == "done" and t["id"] in task.get("depends", [])]
    for t in done:
        parts.append(f"Earlier step '{t['title']}' produced: {clip(t.get('summary', ''), 400)}")
    parts.append(f"This step: {task['title']}")
    fails = [a for a in task.get("attempts", []) if not a.get("passed")]
    if fails:
        parts.append("The last try failed: " + clip(fails[-1].get("failure", ""), 1200))
    if extra:
        parts.append(extra)
    text = "\n\n".join(parts)
    return clip(text, budget)


def grep(workspace, pattern, exts=CODE_EXT, limit=20):
    out = []
    rx = re.compile(pattern)
    for rel in files(workspace, exts):
        try:
            for i, line in enumerate((Path(workspace) / rel).read_text(errors="replace").splitlines(), 1):
                if rx.search(line):
                    out.append(f"{rel}:{i}: {line.strip()[:160]}")
                    if len(out) >= limit:
                        return out
        except OSError:
            pass
    return out
