"""The bare-model condition of the core proof: the same model, tier, sandbox tools and time budget as NEURON, with none
of NEURON's machinery (no routing, plans, specs, templates, solvers, repair search or verification).

A plain tool loop, the way people use a local model as an agent. The model sees the request, the folder's files and the
text of the inputs, and replies with actions:
  WRITE <path> followed by a code block   write a file (any number per reply)
  RUN <command>                           run one shell command in the sandbox (no network); the output comes back
  READ <path>                             show a file
  DONE                                    finished
It stops at DONE, at the time budget, after 3 replies in a row with no action, or after the same reply 3 times in a row.

To keep the comparison conservative (a stronger baseline), the bare model also gets: the contents of the project's text
files up front, the project's test command, the extracted text of the inputs, and for apps NEURON's kit already in place
with its guide and example files (the same material as the builder's BASE condition).

  python3 -m benchmark.proof.bare --task B1_py_invoice --workspace JOB --tier 2gb --max-seconds 600 --report r.json
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
TASKS = HERE / "tasks"

SYSTEM = """You are a capable software and office assistant working alone in a folder on a computer with no internet.
You do the task by replying with actions.

To create or replace a file, write WRITE and the file's path on one line, then the complete file in a code block.
To run a shell command in the folder, write RUN and the command on one line. You will see its output.
To look at a file, write READ and its path on one line.
When the task is complete and checked, write DONE on its own line.

A reply may contain several WRITE actions and then at most one RUN or READ. An example reply:

I will fix the price rounding and run the tests.
WRITE shop/prices.py
```python
def price_with_tax(amount):
    return round(amount * 1.075, 2)
```
RUN python3 -m unittest discover -s tests

Office files (Excel, Word, PowerPoint): WRITE a Python script that makes the file with openpyxl, python-docx or
python-pptx, then RUN the script. Commands have a 120-second limit and no internet. Installed: python3 (with openpyxl,
python-docx, python-pptx, pypdf and reportlab), node, go, g++, curl and the usual Linux tools.
Check your work by running it before you write DONE."""

TEXT_SUFFIXES = {".py", ".js", ".mjs", ".json", ".go", ".mod", ".cpp", ".cc", ".h", ".hpp", ".txt", ".md", ".csv",
                 ".toml", ".cfg", ".ini", ".html", ".css", ".sh", "Makefile", ".yml", ".yaml"}
FILES_CHARS = 14000          # project file contents shown up front
OUTPUT_CHARS = 2500          # command output / file shown per step
CHARS_PER_TOKEN = 3.2


def task_by_id(tid):
    return {t["id"]: t for t in json.loads((TASKS / "tasks.json").read_text())}[tid]


def listing(ws):
    out = []
    for p in sorted(ws.rglob("*")):
        rel = p.relative_to(ws)
        if p.is_file() and not any(part in ("kit", "__pycache__", ".neuron", "node_modules") for part in rel.parts):
            out.append(str(rel))
    return out


def file_contents(ws, files):
    parts, used = [], 0
    for rel in files:
        p = ws / rel
        if (p.suffix in TEXT_SUFFIXES or p.name in TEXT_SUFFIXES) and p.stat().st_size < 40000 and not rel.startswith("inputs/"):
            text = p.read_text(errors="replace")
            if used + len(text) > FILES_CHARS:
                parts.append(f"(more files not shown; READ them if needed)")
                break
            parts.append(f"--- {rel} ---\n{text}")
            used += len(text)
    return "\n".join(parts)


def input_text(path):
    p = Path(path)
    if p.suffix == ".pdf":
        from pypdf import PdfReader
        return "\n".join(f"[page {i}]\n{page.extract_text()}" for i, page in enumerate(PdfReader(str(p)).pages, 1))
    return p.read_text(errors="replace")[:6000]


def first_message(task, ws, attached):
    cat = task["category"]
    parts = [f"Task: {task['request']}"]
    if cat == "app":
        from neuron.builder import prompts
        examples = "\n".join(f"```python\n{prompts.EXAMPLES[k].rstrip()}\n```" for k in ("schema", "entity", "dashboard", "home"))
        parts += ["",
                  "Build the app in the folder app/. It is started with `cd app && python3 app.py`, serves on port 8000 and "
                  "keeps its data in app/data.db. NEURON's kit is already in app/kit and app/app.py already exists: it calls "
                  "schema.setup(app) and the register(app) function of every file in app/pages/. Write app/schema.py and one "
                  "file per page in app/pages/. To try it: RUN cd app && (timeout 60 python3 app.py > server.log 2>&1 &) && "
                  "sleep 3 && curl -s localhost:8000/ | head -40",
                  "", prompts.KIT_GUIDE, "", "# Example files", examples]
    elif cat in ("bug", "feature"):
        parts += ["", f"The project's tests run with: {' '.join(task['test_cmd'])}"]
    else:
        if task["kind"] == "pdf_qa":
            parts += ["", "Write the answers to answers.md in this folder as a numbered list (1., 2., ...), each with its page number."]
        else:
            parts += ["", f"Save {task['output']} in this folder."]
    files = listing(ws)
    parts += ["", "Files in the folder:", "\n".join(files) or "(none)"]
    shown = file_contents(ws, [f for f in files if not f.startswith("app/")])
    if shown:
        parts += ["", shown]
    for a in attached:
        parts += ["", f"--- text of {Path(a).relative_to(ws)} ---", input_text(a)]
    return "\n".join(parts)


def clean_path(p):
    p = p.strip().strip("`'\"*").strip()
    p = re.sub(r"^\./", "", p)
    if not p or p.startswith("/") or ".." in Path(p).parts:
        return None
    return p


WRITE_RE = re.compile(r"^[ \t>*#]*WRITE[:\s]+`?([^\s`]+)`?[^\n]*\n+```[^\n]*\n(.*?)\n?```", re.M | re.S)
LINE_RE = re.compile(r"^[ \t>*#`]*(RUN|READ|DONE)\b[: \t]*(.*)$", re.M)


def parse(text):
    writes = [(clean_path(m.group(1)), m.group(2)) for m in WRITE_RE.finditer(text)]
    rest = WRITE_RE.sub("", text)
    action = None
    for m in LINE_RE.finditer(rest):
        word, arg = m.group(1), m.group(2).strip().strip("`").strip()
        if word == "RUN" and not arg:                     # RUN followed by a code block
            block = re.match(r"\s*```[^\n]*\n(.*?)```", rest[m.end():], re.S)
            arg = block.group(1).strip() if block else ""
        if word == "DONE" or arg:
            action = (word, arg)
            if word != "DONE":
                break
    return [w for w in writes if w[0]], action


def fit(messages, max_prompt_tokens):
    """Keep the system message and the task; drop the oldest steps until the prompt fits the context."""
    head, steps = messages[:2], messages[2:]
    size = lambda ms: sum(len(m["content"]) for m in ms) / CHARS_PER_TOKEN
    dropped = False
    while steps and size(head + steps) > max_prompt_tokens:
        steps = steps[2:]
        dropped = True
    if dropped and steps and steps[0]["role"] == "assistant":
        steps = [{"role": "user", "content": "(earlier steps omitted to fit the memory)"}] + steps
    while size(head + steps) > max_prompt_tokens and len(head[1]["content"]) > 2000:    # the task alone is too long
        head[1] = {"role": "user", "content": head[1]["content"][: int(len(head[1]["content"]) * 0.8)]}
    return head + steps


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--tier", required=True)
    ap.add_argument("--max-seconds", type=float, required=True)
    ap.add_argument("--attach", nargs="*", default=[])
    ap.add_argument("--report", required=True)
    a = ap.parse_args(argv)
    t0 = time.time()
    from neuron.brain.llm import LLMUnavailable
    from neuron.brain.models import ModelManager, ModelRunner
    from neuron.brain.sandbox import Sandbox
    task, ws = task_by_id(a.task), Path(a.workspace).resolve()
    ws.mkdir(parents=True, exist_ok=True)
    attached = []
    for f in a.attach:                                    # inputs are copied into the job, as NEURON does
        dst = ws / "inputs" / Path(f).name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(Path(f).read_bytes())
        attached.append(str(dst))
    if task["category"] == "app":
        from neuron.builder.build import prepare_project
        from neuron.design import engine
        prepare_project(ws / "app", design=True)          # the same kit and design engine NEURON's builder uses
        (ws / "app" / "theme.json").write_text(json.dumps(engine.choose(task["request"]), indent=1))
    manager = ModelManager()
    runner = ModelRunner(manager, a.tier, log_dir=ws / ".bare")
    (ws / ".bare").mkdir(exist_ok=True)
    ctx = manager.get(runner.model_for("builder")).get("context_tokens", 8192)
    max_tokens = 3000 if task["category"] == "app" else 2048
    sandbox = Sandbox(timeout=120, mem_mb=1024, toolchains=True)
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": first_message(task, ws, attached)}]
    rep = {"task": a.task, "condition": "bare", "model": runner.model_for("builder"), "turns": 0, "writes": 0, "runs": 0,
           "reads": 0, "model_calls": 0, "tokens": 0, "model_seconds": 0.0, "claimed_done": False, "ended": "", "errors": []}
    transcript = ws / ".bare" / "transcript.jsonl"
    idle, last_text, repeats = 0, None, 0
    try:
        while True:
            if time.time() - t0 > a.max_seconds:
                rep["ended"] = "time budget used up"
                break
            client = runner.client("builder")
            try:
                reply = client.chat(fit(messages, ctx - max_tokens - 256), max_tokens=max_tokens, temperature=0.2)
            except LLMUnavailable as e:
                rep["errors"].append(str(e)[:200])
                if len(rep["errors"]) >= 3:
                    rep["ended"] = "model errors"
                    break
                continue
            rep["model_calls"] += 1
            rep["tokens"] += reply.prompt_tokens + reply.completion_tokens
            rep["model_seconds"] += reply.seconds
            rep["turns"] += 1
            text = reply.text
            with open(transcript, "a") as f:
                f.write(json.dumps({"turn": rep["turns"], "reply": text, "finish": reply.finish_reason}) + "\n")
            repeats = repeats + 1 if text == last_text else 0
            last_text = text
            if repeats >= 2:
                rep["ended"] = "the same reply 3 times in a row"
                break
            writes, action = parse(text)
            feedback = []
            for path, content in writes:
                dest = ws / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content.rstrip("\n") + "\n")
                rep["writes"] += 1
                feedback.append(f"Wrote {path}.")
            if reply.finish_reason == "length":
                feedback.append("Your reply was cut off at the length limit; the last file may be incomplete. Write long files in smaller parts.")
            if action and action[0] == "RUN":
                r = sandbox.run(["bash", "-c", action[1]], ws, timeout=120)
                rep["runs"] += 1
                out = r.output[-OUTPUT_CHARS:]
                feedback.append(f"$ {action[1]}\n{out}\n(exit code {r.exit_code}{', timed out' if r.timed_out else ''})")
            elif action and action[0] == "READ":
                p = clean_path(action[1])
                rep["reads"] += 1
                if p and (ws / p).is_file():
                    feedback.append(f"--- {p} ---\n{(ws / p).read_text(errors='replace')[:OUTPUT_CHARS]}")
                else:
                    feedback.append(f"There is no file {action[1]}.")
            elif action and action[0] == "DONE":
                rep["claimed_done"] = True
                rep["ended"] = "the model said DONE"
                break
            if not writes and not action:
                idle += 1
                if idle >= 3:
                    rep["ended"] = "3 replies in a row with no action"
                    break
                feedback.append("Reply with WRITE, RUN, READ or DONE as described.")
            else:
                idle = 0
            messages += [{"role": "assistant", "content": text}, {"role": "user", "content": "\n\n".join(feedback)}]
    finally:
        runner.unload()
        rep["seconds"] = round(time.time() - t0, 1)
        rep["model_seconds"] = round(rep["model_seconds"], 1)
        rep["model_loads"] = runner.loads
        Path(a.report).write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep), flush=True)


if __name__ == "__main__":
    main()
