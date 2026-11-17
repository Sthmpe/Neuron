"""Spreadsheets. The model decides WHAT to summarise (group by which column, which measures); code writes
real Excel formulas and a spreadsheet application recalculates them to prove the numbers."""
import csv
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..capability import Capability, Outcome, Verdict

OPS = ("sum", "sum_product", "count", "average")


def soffice(args, timeout=180):
    home = tempfile.mkdtemp(prefix="lo-")
    env = {**{k: v for k, v in os.environ.items() if "proxy" not in k.lower()}, "HOME": home}
    try:
        return subprocess.run(["soffice", "--headless", "--norestore", f"-env:UserInstallation=file://{home}"] + args,
                              capture_output=True, text=True, timeout=timeout, env=env)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def load_table(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        rows = list(csv.reader(open(path, newline="", encoding="utf-8-sig")))
        return rows[0], rows[1:]
    from openpyxl import load_workbook
    ws = load_workbook(path, data_only=True).active
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    return [str(c) for c in rows[0]], rows[1:]


def as_number(v):
    if isinstance(v, (int, float)):
        return v
    try:
        f = float(str(v).replace(",", ""))
        return int(f) if f.is_integer() and "." not in str(v) else f
    except ValueError:
        return None


def column_letter(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


class ReadTables(Capability):
    name = "read_tables"
    purpose = "Read attached CSV or Excel tables: columns, types, row count, sample rows"
    outputs = ["table schema"]
    requires = {"binaries": [], "modules": ["openpyxl"]}
    verification = "deterministic parse"
    domains = ("data", "documents")

    def run(self, job, params):
        tables = []
        for a in job.state.goal().get("attachments", []):
            p = Path(a)
            if p.suffix.lower() not in (".csv", ".xlsx"):
                continue
            header, rows = load_table(p)
            types = {}
            for i, h in enumerate(header):
                vals = [r[i] for r in rows if i < len(r) and r[i] not in (None, "")]
                types[h] = "number" if vals and all(as_number(v) is not None for v in vals) else "text"
            tables.append({"path": str(p), "name": p.name, "columns": header, "types": types, "rows": len(rows), "sample": rows[:3]})
        if not tables:
            return Outcome(False, "no CSV or Excel file is attached", evidence={"no_retry": True})
        return Outcome(True, "; ".join(f"{t['name']}: {t['rows']} rows, columns {', '.join(t['columns'])}" for t in tables), {"tables": tables})

    def verify(self, job, params, outcome):
        return Verdict(True, [{"id": "parsed", "pass": True, "detail": outcome.summary}], "deterministic")


class PlanWorkbook(Capability):
    name = "plan_workbook"
    purpose = "Decide the workbook's sheets, the summary grouping and the measures (sum, sum of products, count, average)"
    permissions = ("read_workspace", "use_model")
    resources = {"ram_mb": 50, "uses_model": True}
    verification = "every column named exists in the data and every operation is supported"
    domains = ("data", "documents")
    strategies = ("ask again with the problems listed",)

    def run(self, job, params):
        t = job.state.task("inputs")["result"]["tables"][0]
        req = job.state.goal()["request"]
        numeric = [c for c, ty in t["types"].items() if ty == "number"]
        text = [c for c, ty in t["types"].items() if ty == "text"]
        schema = {"type": "object", "required": ["group_by", "measures", "total_row", "share_of"],
                  "properties": {"group_by": {"type": "string", "enum": text or t["columns"]},
                                 "measures": {"type": "array", "minItems": 1, "maxItems": 5, "items": {
                                     "type": "object", "required": ["label", "op", "columns"],
                                     "properties": {"label": {"type": "string"}, "op": {"type": "string", "enum": list(OPS)},
                                                    "columns": {"type": "array", "maxItems": 2, "items": {"type": "string", "enum": numeric or t["columns"]}}}}},
                                 "total_row": {"type": "boolean"}, "share_of": {"type": "string"}}}
        user = (f"Request: {req}\n\nData columns: {', '.join(f'{c} ({t['types'][c]})' for c in t['columns'])}\n"
                f"Sample rows: {t['sample'][:2]}\n\nDecide the summary: which column to group rows by, and the measures to show for each group. "
                "op sum adds one column; sum_product adds the product of two columns per row (for example units times price); "
                "count counts rows; average averages one column. share_of: the label of a measure to also show as each group's "
                "percentage of the total, or empty." + (f"\nProblems last time: {params['feedback']}" if params.get("feedback") else ""))
        plan = job.ask_json("planner", "You design spreadsheet summaries.", user, schema, max_tokens=400)
        if not plan:
            return Outcome(False, "the model gave no usable plan")
        names = re.findall(r"\b([\w-]+\.xlsx)\b", req)
        plan["file"] = names[0] if names else "workbook.xlsx"
        sheets = re.findall(r"sheet (?:called|named) (\w+)", req, re.I)
        plan["data_sheet"] = sheets[0] if sheets else "Data"
        plan["summary_sheet"] = sheets[1] if len(sheets) > 1 else "Summary"
        plan["source"] = t["path"]
        return Outcome(True, f"group by {plan['group_by']}; measures {[m['label'] + '=' + m['op'] for m in plan['measures']]}", plan, made_by="model")

    def verify(self, job, params, outcome):
        p, cols = outcome.result, job.state.task("inputs")["result"]["tables"][0]["columns"]
        checks = [{"id": "group_column_exists", "pass": p.get("group_by") in cols, "detail": p.get("group_by")}]
        for m in p.get("measures", []):
            need = 2 if m["op"] == "sum_product" else 0 if m["op"] == "count" else 1
            ok = m["op"] in OPS and all(c in cols for c in m.get("columns", [])) and len(m.get("columns", [])) >= need
            checks.append({"id": f"measure_{m.get('label')}", "pass": ok, "detail": str(m)})
        labels = [m["label"] for m in p.get("measures", [])]
        if p.get("share_of"):
            checks.append({"id": "share_refers_to_a_measure", "pass": p["share_of"] in labels, "detail": p["share_of"]})
        return Verdict(all(c["pass"] for c in checks), checks, "plan validated against the data")


class WriteWorkbook(Capability):
    name = "write_workbook"
    purpose = "Write the workbook: the data sheet and a summary sheet whose numbers are real formulas"
    permissions = ("read_workspace", "write_workspace")
    requires = {"binaries": [], "modules": ["openpyxl"]}
    verification = "the file opens and every summary cell is a formula"
    domains = ("data", "documents")

    def run(self, job, params):
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        p = job.state.task("design")["result"]
        header, rows = load_table(p["source"])
        wb = Workbook()
        d = wb.active
        d.title = p["data_sheet"]
        d.append(header)
        for r in rows:
            d.append([as_number(v) if as_number(v) is not None else v for v in r])
        n = len(rows) + 1
        col = {h: column_letter(i) for i, h in enumerate(header)}
        rng = lambda c: f"{p['data_sheet']}!${col[c]}$2:${col[c]}${n}"
        s = wb.create_sheet(p["summary_sheet"])
        labels = [m["label"] for m in p["measures"]]
        heads = [p["group_by"].replace("_", " ").capitalize()] + labels + ([f"Share of {p['share_of'].lower()}"] if p.get("share_of") else [])
        s.append(heads)
        groups = sorted({str(r[header.index(p["group_by"])]) for r in rows})
        total_row = len(groups) + 2
        for gi, g in enumerate(groups, 2):
            line = [g]
            for m in p["measures"]:
                key = f"$A{gi}"
                if m["op"] == "sum":
                    line.append(f"=SUMIF({rng(p['group_by'])},{key},{rng(m['columns'][0])})")
                elif m["op"] == "sum_product":
                    a, b = m["columns"][:2]
                    line.append(f"=SUMPRODUCT(({rng(p['group_by'])}={key})*{rng(a)}*{rng(b)})")
                elif m["op"] == "count":
                    line.append(f"=COUNTIF({rng(p['group_by'])},{key})")
                else:
                    line.append(f"=AVERAGEIF({rng(p['group_by'])},{key},{rng(m['columns'][0])})")
            if p.get("share_of"):
                c = column_letter(labels.index(p["share_of"]) + 1)
                line.append(f"={c}{gi}/{c}${total_row}")
            s.append(line)
        if p.get("total_row", True):
            tl = ["Total"]
            for i, m in enumerate(p["measures"], 1):
                c = column_letter(i)
                tl.append(f"=SUM({c}2:{c}{total_row - 1})" if m["op"] != "average" else f"=AVERAGE({rng(m['columns'][0])})")
            if p.get("share_of"):
                c = column_letter(len(labels) + 1)
                tl.append(f"=SUM({c}2:{c}{total_row - 1})")
            s.append(tl)
        bold, tone = Font(bold=True), PatternFill("solid", fgColor="EEF2F6")
        for ws in (d, s):
            for c in ws[1]:
                c.font, c.fill, c.alignment = bold, tone, Alignment(horizontal="left")
            ws.freeze_panes = "A2"
            for i, h in enumerate(ws[1]):
                ws.column_dimensions[column_letter(i)].width = max(12, len(str(h.value)) + 4)
        for row in s.iter_rows(min_row=2):
            for i, c in enumerate(row[1:], 1):
                if p.get("share_of") and i == len(labels) + 1:
                    c.number_format = "0.0%"
                elif i <= len(labels) and p["measures"][i - 1]["op"] != "count":
                    c.number_format = "#,##0.00"
        for c in s[total_row]:
            c.font = bold
        out = job.workspace / p["file"]
        wb.save(out)
        return Outcome(True, f"wrote {p['file']}: {len(rows)} data rows, {len(groups)} groups", {"file": p["file"], "groups": groups}, [p["file"]], made_by="template")

    def verify(self, job, params, outcome):
        from openpyxl import load_workbook
        p = job.state.task("design")["result"]
        wb = load_workbook(job.workspace / outcome.result["file"])
        cells = [c.value for row in wb[p["summary_sheet"]].iter_rows(min_row=2) for c in row[1:]]
        ok = cells and all(isinstance(v, str) and v.startswith("=") for v in cells if v is not None)
        return Verdict(bool(ok), [{"id": "summary_cells_are_formulas", "pass": bool(ok), "detail": f"{len(cells)} cells"}], "openpyxl")


class CheckWorkbook(Capability):
    name = "check_workbook"
    purpose = "Recalculate the workbook in a spreadsheet application and compare every number with the data"
    requires = {"binaries": ["soffice"], "modules": ["openpyxl"]}
    verification = "LibreOffice recalculation; each group's numbers recomputed independently from the source data"
    domains = ("data", "documents")

    def run(self, job, params):
        from openpyxl import load_workbook
        p = job.state.task("design")["result"]
        f = job.workspace / p["file"]
        out = Path(tempfile.mkdtemp(prefix="recalc-"))
        soffice(["--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", str(out), str(f)])
        if not (out / f.name).exists():
            return Outcome(False, "the spreadsheet application could not open the file")
        grid = list(load_workbook(out / f.name, data_only=True)[p["summary_sheet"]].iter_rows(values_only=True))
        shutil.rmtree(out, ignore_errors=True)
        return Outcome(True, f"recalculated {len(grid) - 1} rows", {"grid": [[c for c in r] for r in grid]})

    def verify(self, job, params, outcome):
        p = job.state.task("design")["result"]
        header, rows = load_table(p["source"])
        gi = header.index(p["group_by"])
        checks = []
        grid = outcome.result["grid"]
        errors = [c for r in grid for c in r if isinstance(c, str) and c.startswith("#")]
        checks.append({"id": "no_formula_errors", "pass": not errors, "detail": errors[:3]})
        for row in grid[1:]:
            g = str(row[0])
            if g.lower() == "total":
                continue
            mine = [r for r in rows if str(r[gi]) == g]
            for k, m in enumerate(p["measures"], 1):
                cols = [header.index(c) for c in m.get("columns", [])]
                if m["op"] == "sum":
                    want = sum(as_number(r[cols[0]]) or 0 for r in mine)
                elif m["op"] == "sum_product":
                    want = sum((as_number(r[cols[0]]) or 0) * (as_number(r[cols[1]]) or 0) for r in mine)
                elif m["op"] == "count":
                    want = len(mine)
                else:
                    want = sum(as_number(r[cols[0]]) or 0 for r in mine) / max(1, len(mine))
                got = row[k] if k < len(row) else None
                checks.append({"id": f"{g}_{m['label']}", "pass": isinstance(got, (int, float)) and abs(got - want) < 0.01, "detail": f"{got} vs {want:.2f}"})
        return Verdict(all(c["pass"] for c in checks), checks, "spreadsheet application recalculation vs independent computation")


CAPABILITIES = [ReadTables(), PlanWorkbook(), WriteWorkbook(), CheckWorkbook()]
