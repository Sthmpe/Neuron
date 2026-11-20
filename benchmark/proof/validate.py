"""Validate every core-proof examiner before the lock: a correct reference must pass all its checks, and a wrong or
empty delivery must fail.

  python3 -m benchmark.proof.validate            (all)      python3 -m benchmark.proof.validate --only A1_pharmacy
"""
import argparse
import csv
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.proof.defs_apps import APPS            # noqa: E402
from benchmark.proof.defs_bugs import BUGS            # noqa: E402
from benchmark.proof.defs_features import FEATURES    # noqa: E402
from benchmark.proof.examine import TASKS, examine    # noqa: E402

TASK_LIST = {t["id"]: t for t in json.loads((TASKS / "tasks.json").read_text())}


def tmp():
    return Path(tempfile.mkdtemp(prefix="proofval-"))


# ---- references -------------------------------------------------------------------------------------------------
def ref_app(a, project):
    """A template build of the correct plan (the builder with a scripted planner): what a right answer looks like."""
    from neuron.brain.sandbox import Sandbox
    from neuron.builder import templates
    from neuron.builder.build import build_full
    from tests.fakes import ScriptedLLM

    class Runner:
        loads = 1

        def __init__(self, llm):
            self.llm = llm

        def client(self, role):
            return self.llm

        def model_for(self, role):
            return "scripted"

    def reply(messages):
        sys_, last = messages[0]["content"], messages[-1]["content"]
        if sys_.startswith("You turn a plain-language request"):
            return json.dumps(a["reference"])
        if "check a web page against" in sys_:
            return '{"ok": true, "missing": []}'
        m = re.search(r"# Your task: (\S+)", last)
        st = json.loads((project / ".neuron" / "spec.json").read_text())["spec"]
        return "```python\n" + templates.reference_files(st)[m.group(1)] + "```" if m else "ok"
    r = build_full(project, a["request"], Runner(ScriptedLLM([reply] * 80)), Sandbox(timeout=60, mem_mb=256), log=lambda *_: None, design=True)
    if r.get("ok"):
        return "template build"
    # NEURON's builder can reject its own correct template (found here for A5: with a refusing stock rule its dashboard
    # self-check expects the wrong count). That is a NEURON defect, deliberately NOT fixed before the runs (no tuning on
    # this set); for validating the EXAMINER the same template files are written directly, without the self-check.
    from neuron.builder.build import prepare_project
    from neuron.builder.spec import normalise
    spec = json.loads((project / ".neuron" / "spec.json").read_text())["spec"]
    for rel, code in templates.reference_files(spec).items():
        (project / rel).parent.mkdir(parents=True, exist_ok=True)
        (project / rel).write_text(code)
    return "templates written directly (builder self-check rejected the correct template)"


def ref_code(t, folder):
    shutil.copytree(TASKS / TASK_LIST[t["id"]]["workspace"], folder)
    for path, (old, new) in t.get("fix", {}).items():
        text = (folder / path).read_text()
        assert old in text, (t["id"], old)
        (folder / path).write_text(text.replace(old, new))
    for path, text in {**t.get("fix_file", {}), **t.get("reference", {})}.items():
        (folder / path).parent.mkdir(parents=True, exist_ok=True)
        (folder / path).write_text(text)


def ref_excel(t, folder):
    from openpyxl import Workbook
    rows = list(csv.DictReader(open(TASKS / t["inputs"][0])))
    cols = list(rows[0].keys())
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(cols)
    for r in rows:
        ws.append([float(r[c]) if re.fullmatch(r"\d+(\.\d+)?", r[c]) else r[c] for c in cols])
    n = len(rows) + 1
    letter = {c: chr(65 + i) for i, c in enumerate(cols)}
    group = t["args"][0]
    s = wb.create_sheet("Summary")
    groups = sorted({r[group] for r in rows})
    g = letter[group]
    if t["kind"] == "excel_products":
        q, p = letter[t["args"][1]], letter[t["args"][2]]
        s.append([group.title(), "Total " + t["args"][1], "Total value"])
        for i, name in enumerate(groups, 2):
            s.append([name, f"=SUMIF(Data!{g}2:{g}{n},A{i},Data!{q}2:{q}{n})",
                      f"=SUMPRODUCT((Data!{g}2:{g}{n}=A{i})*Data!{q}2:{q}{n}*Data!{p}2:{p}{n})"])
        last = len(groups) + 1
        s.append(["Total", f"=SUM(B2:B{last})", f"=SUM(C2:C{last})"])
    else:
        v = letter[t["args"][1]]
        s.append([group.title(), "Total"])
        for i, name in enumerate(groups, 2):
            s.append([name, f"=SUMIF(Data!{g}2:{g}{n},A{i},Data!{v}2:{v}{n})"])
        s.append(["Total", f"=SUM(B2:B{len(groups) + 1})"])
    wb.save(folder / t["output"])


def ref_word(t, folder):
    import docx
    w = t["word"]
    doc = docx.Document()
    doc.add_heading(t["output"].replace("_", " ").replace(".docx", "").title(), 0)
    target = (w["words"][0] + w["words"][1]) // 2
    sentence = "This section explains the matter clearly and states what is needed and by when. "
    per = max(1, target // (len(w["headings"]) * len(sentence.split())))
    for h in w["headings"]:
        doc.add_heading(h, 1)
        doc.add_paragraph(sentence * per)
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text, table.rows[0].cells[1].text = w["table"]["header"]
    for k, v in list(w["table"]["rows"].items()) + [("Total", sum(w["table"]["rows"].values()))]:
        c = table.add_row().cells
        c[0].text, c[1].text = k, str(v)
    doc.save(folder / t["output"])


def ref_pptx(t, folder):
    from pptx import Presentation
    p = t["pptx"]
    prs = Presentation()
    for i in range(p["slides"]):
        s = prs.slides.add_slide(prs.slide_layouts[1])
        s.shapes.title.text = f"Slide {i + 1}" if i else "Welcome"
        tf = s.placeholders[1].text_frame
        tf.text = " and ".join(p["must_contain"]) if i == 1 else "A short point for this slide"
        tf.add_paragraph().text = "A second point"
    prs.save(folder / t["output"])


def ref_pdf(t, folder):
    (folder / "answers.md").write_text("\n".join(f"{i + 1}. {q['expect'][0]} (riverside clinic report 2026, page {q['page']})"
                                                for i, q in enumerate(t["questions"])) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    a = ap.parse_args()
    results = {}

    def expect(tid, folder, should_pass, label):
        r = examine(TASK_LIST[tid], folder)
        ok = r["solved"] == should_pass
        results[f"{tid} {label}"] = {"as_expected": ok, "score": f"{r['passed']}/{r['total']}", "failed": [c["id"] for c in r["checks"] if not c["pass"]][:6]}
        print(f"{'OK ' if ok else 'BAD'} {tid} {label}: {r['passed']}/{r['total']}" + ("" if ok else f" {results[f'{tid} {label}']['failed']}"), flush=True)

    sel = lambda tid: not a.only or tid == a.only
    for app in APPS:
        if sel(app["id"]):
            p = tmp() / "app"
            if ref_app(app, p):
                expect(app["id"], p.parent, True, "reference app")
            else:
                results[f"{app['id']} reference app"] = {"as_expected": False, "score": "build failed"}
                print("BAD", app["id"], "reference build failed")
            expect(app["id"], tmp(), False, "nothing delivered")
    for t in BUGS + FEATURES:
        if sel(t["id"]):
            f = tmp() / "p"
            ref_code(t, f)
            expect(t["id"], f, True, "reference")
            expect(t["id"], TASKS / TASK_LIST[t["id"]]["workspace"], False, "as shipped")
    for tid, t in TASK_LIST.items():
        if t["category"] != "document" or not sel(tid):
            continue
        f = tmp()
        {"excel_products": ref_excel, "excel_simple": ref_excel, "word": ref_word, "pptx": ref_pptx, "pdf_qa": ref_pdf}[t["kind"]](t, f)
        expect(tid, f, True, "reference")
        expect(tid, tmp(), False, "nothing delivered")
    if not a.only:
        (HERE / "validation.json").write_text(json.dumps(results, indent=1))
    bad = [k for k, v in results.items() if not v["as_expected"]]
    print("VALIDATION", "PASSED" if not bad else f"FAILED: {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
