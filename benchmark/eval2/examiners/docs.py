"""Independent checkers for document deliverables. They open the files with their own parsers and, where a
real application is needed (formula recalculation, slide rendering), with LibreOffice in headless mode.
Each returns {"checks": [{"id", "pass", "detail"}], "passed", "total"}."""
import csv
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

EM = re.compile(r"[—―]")


def _result(checks):
    return {"checks": checks, "passed": sum(c["pass"] for c in checks), "total": len(checks)}


def _soffice(args, timeout=180):
    home = tempfile.mkdtemp(prefix="lo-")
    env = {**{k: v for k, v in os.environ.items() if "proxy" not in k.lower()}, "HOME": home}
    try:
        return subprocess.run(["soffice", "--headless", "--norestore", f"-env:UserInstallation=file://{home}"] + args,
                              capture_output=True, text=True, timeout=timeout, env=env)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def _num(text):
    return re.sub(r"[,\s]", "", str(text))


# ---- PDF research --------------------------------------------------------------------------------
def pdf_qa(answers, task, sources_dir):
    """answers: list of answer strings, one per question, in order."""
    from pypdf import PdfReader
    pages = {}
    for rel in task["inputs"]:
        name = Path(rel).stem
        pages[name] = [p.extract_text() or "" for p in PdfReader(Path(sources_dir) / Path(rel).name).pages]
    checks = []
    for i, q in enumerate(task["questions"]):
        a = answers[i] if i < len(answers) else ""
        flat = _num(a).lower()
        facts = all(_num(e).lower() in flat for e in q["expect"])
        doc = next(n for n in pages if n.startswith(q["doc"]))
        cites = re.search(rf"\b(?:page|p\.?|pg\.?)\s*{q['page']}\b", a, re.I) is not None
        names_doc = any(w in a.lower() for w in q["doc"].replace("_", " ").split())
        checks.append({"id": f"q{i + 1}_answer_correct", "pass": facts, "detail": a[:200]})
        checks.append({"id": f"q{i + 1}_cites_right_page", "pass": cites and names_doc, "detail": f"needs {q['doc']} page {q['page']}"})
    return _result(checks)


# ---- Excel ----------------------------------------------------------------------------------------
def excel(path, csv_path, region_col="region"):
    from openpyxl import load_workbook
    checks = []
    path = Path(path)
    if not path.exists():
        return _result([{"id": "file_exists", "pass": False, "detail": str(path)}])
    rows = list(csv.DictReader(open(csv_path)))
    truth = {}
    for r in rows:
        t = truth.setdefault(r[region_col], [0, 0.0])
        t[0] += int(r["units"]); t[1] += int(r["units"]) * float(r["unit_price"])
    total_rev = sum(v[1] for v in truth.values())
    wb = load_workbook(path)                       # formulas as written
    checks.append({"id": "has_data_and_summary_sheets", "pass": {"Data", "Summary"} <= set(wb.sheetnames), "detail": str(wb.sheetnames)})
    if "Data" in wb.sheetnames:
        n = sum(1 for row in wb["Data"].iter_rows(min_row=2, values_only=True) if any(v is not None for v in row))
        checks.append({"id": "data_sheet_has_all_rows", "pass": n == len(rows), "detail": f"{n} of {len(rows)}"})
    formulas = []
    if "Summary" in wb.sheetnames:
        for row in wb["Summary"].iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    formulas.append(c.value)
    checks.append({"id": "summary_uses_formulas", "pass": len(formulas) >= len(truth) * 2, "detail": f"{len(formulas)} formulas"})
    checks.append({"id": "formulas_refer_to_data_sheet", "pass": any("Data" in f for f in formulas), "detail": formulas[:3]})
    # recalculate with a real spreadsheet application, then read the computed values
    out = Path(tempfile.mkdtemp(prefix="recalc-"))
    r = _soffice(["--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", str(out), str(path)])
    recalced = out / path.name
    if not recalced.exists():
        checks.append({"id": "recalculates_in_spreadsheet_app", "pass": False, "detail": (r.stderr or r.stdout)[-300:]})
        return _result(checks)
    vals = load_workbook(recalced, data_only=True)
    s = vals["Summary"] if "Summary" in vals.sheetnames else None
    errors = [c.value for row in (s.iter_rows() if s else []) for c in row if isinstance(c.value, str) and c.value.startswith("#")]
    checks.append({"id": "no_formula_errors", "pass": s is not None and not errors, "detail": errors[:3]})
    grid = [[c for c in row] for row in s.iter_rows(values_only=True)] if s else []
    for region, (units, rev) in sorted(truth.items()):
        row = next((r for r in grid if any(isinstance(c, str) and c.strip().lower() == region.lower() for c in r)), None)
        nums = [c for c in (row or []) if isinstance(c, (int, float))]
        ok_units = any(abs(n - units) < 0.01 for n in nums)
        ok_rev = any(abs(n - rev) < 0.01 for n in nums)
        share = rev / total_rev
        ok_share = any(abs(n - share) < 0.0005 or abs(n - share * 100) < 0.05 for n in nums)
        checks.append({"id": f"{region.lower()}_totals_correct", "pass": ok_units and ok_rev, "detail": f"want {units} units, {rev:.2f}; row {row}"})
        checks.append({"id": f"{region.lower()}_share_correct", "pass": ok_share, "detail": f"want {share:.4f}"})
    total_row = next((r for r in grid if r and isinstance(r[0], str) and r[0].strip().lower().startswith("total")), None)
    checks.append({"id": "total_row_correct", "pass": bool(total_row) and any(isinstance(c, (int, float)) and abs(c - total_rev) < 0.01 for c in total_row),
                   "detail": f"want {total_rev:.2f}; row {total_row}"})
    shutil.rmtree(out, ignore_errors=True)
    return _result(checks)


# ---- Word -----------------------------------------------------------------------------------------
def word(path, headings, table=None, words=(400, 900)):
    from docx import Document
    path = Path(path)
    if not path.exists():
        return _result([{"id": "file_exists", "pass": False, "detail": str(path)}])
    d = Document(path)
    paras = d.paragraphs
    found = [p.text.strip() for p in paras if p.style.name.lower().startswith("heading") and p.text.strip()]
    order = [h for h in found if h.lower() in [x.lower() for x in headings]]
    checks = [{"id": "headings_present_in_order", "pass": [h.lower() for h in order] == [x.lower() for x in headings], "detail": found}]
    text = "\n".join(p.text for p in paras) + "\n" + "\n".join(c.text for t in d.tables for r in t.rows for c in r.cells)
    n = len(re.findall(r"\b\w+\b", "\n".join(p.text for p in paras)))
    checks.append({"id": "length_in_range", "pass": words[0] <= n <= words[1], "detail": f"{n} words"})
    checks.append({"id": "no_em_dashes", "pass": not EM.search(text), "detail": ""})
    checks.append({"id": "no_placeholders", "pass": not re.search(r"lorem ipsum|\bTBD\b|\[insert|\bXXX\b", text, re.I), "detail": ""})
    if table:
        ok, detail = False, "no table found"
        for t in d.tables:
            cells = [[c.text.strip() for c in r.cells] for r in t.rows]
            if not cells or [h.lower() for h in cells[0][:2]] != [h.lower() for h in table["header"]]:
                continue
            body = {r[0].lower(): r[1] for r in cells[1:] if len(r) >= 2}
            rows_ok = all(any(k.lower() in name for name in body) and _num(body[next(name for name in body if k.lower() in name)]).split(".")[0] == str(v)
                          for k, v in table["rows"].items())
            total_key = next((name for name in body if name.startswith("total")), None)
            total_ok = total_key is not None and _num(body[total_key]).split(".")[0] == str(sum(table["rows"].values()))
            ok, detail = rows_ok and total_ok, str(cells)
            break
        checks.append({"id": "budget_table_correct", "pass": ok, "detail": detail[:300]})
    return _result(checks)


# ---- PowerPoint -----------------------------------------------------------------------------------
def pptx(path, slides, must_contain=(), max_bullets=5):
    from pptx import Presentation
    from pptx.util import Pt
    path = Path(path)
    if not path.exists():
        return _result([{"id": "file_exists", "pass": False, "detail": str(path)}])
    pres = Presentation(path)
    checks = [{"id": "slide_count", "pass": len(pres.slides) == slides, "detail": len(pres.slides)}]
    all_text, titles, too_many, small = [], [], [], []
    W, H = pres.slide_width, pres.slide_height
    off = []
    for i, s in enumerate(pres.slides, 1):
        title = s.shapes.title.text.strip() if s.shapes.title is not None and s.shapes.title.has_text_frame else ""
        titles.append(title)
        bullets = 0
        for sh in s.shapes:
            if sh.left is not None and (sh.left < 0 or sh.top < 0 or sh.left + sh.width > W or sh.top + sh.height > H):
                off.append(i)
            if not sh.has_text_frame:
                continue
            for p in sh.text_frame.paragraphs:
                t = "".join(r.text for r in p.runs).strip()
                if not t:
                    continue
                all_text.append(t)
                if sh != s.shapes.title:
                    bullets += 1
                for r in p.runs:
                    if r.font.size is not None and r.font.size < Pt(14):
                        small.append(i)
        if bullets > max_bullets + 1:
            too_many.append(i)
    text = "\n".join(all_text)
    checks.append({"id": "every_slide_has_a_title", "pass": all(titles), "detail": titles})
    checks.append({"id": "slides_kept_short", "pass": not too_many, "detail": too_many})
    checks.append({"id": "readable_font_sizes", "pass": not small, "detail": sorted(set(small))})
    checks.append({"id": "shapes_inside_the_slide", "pass": not off, "detail": sorted(set(off))})
    checks.append({"id": "no_em_dashes", "pass": not EM.search(text), "detail": ""})
    for m in must_contain:
        checks.append({"id": f"mentions_{re.sub(r'[^a-z0-9]+', '_', m.lower())}", "pass": _num(m).lower() in _num(text).lower(), "detail": ""})
    out = Path(tempfile.mkdtemp(prefix="render-"))
    _soffice(["--convert-to", "pdf", "--outdir", str(out), str(path)])
    pdf = out / (path.stem + ".pdf")
    pages = 0
    if pdf.exists():
        from pypdf import PdfReader
        pages = len(PdfReader(pdf).pages)
    checks.append({"id": "renders_in_presentation_app", "pass": pages == slides, "detail": f"{pages} rendered pages"})
    shutil.rmtree(out, ignore_errors=True)
    return _result(checks)


def excel_simple(path, csv_path, group_col, value_col):
    """Dev variant: totals of value_col per group_col on a Summary sheet, with formulas and a Total row."""
    from openpyxl import load_workbook
    path = Path(path)
    if not path.exists():
        return _result([{"id": "file_exists", "pass": False, "detail": str(path)}])
    rows = list(csv.DictReader(open(csv_path)))
    truth = {}
    for r in rows:
        truth[r[group_col]] = truth.get(r[group_col], 0) + float(r[value_col])
    wb = load_workbook(path)
    checks = [{"id": "has_data_and_summary_sheets", "pass": {"Data", "Summary"} <= set(wb.sheetnames), "detail": wb.sheetnames}]
    f = [c.value for row in wb["Summary"].iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=")] if "Summary" in wb.sheetnames else []
    checks.append({"id": "summary_uses_formulas", "pass": len(f) >= len(truth), "detail": len(f)})
    out = Path(tempfile.mkdtemp(prefix="recalc-"))
    _soffice(["--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", str(out), str(path)])
    if not (out / path.name).exists() or "Summary" not in wb.sheetnames:
        checks.append({"id": "recalculated_values_correct", "pass": False, "detail": "could not recalculate"})
        return _result(checks)
    grid = list(load_workbook(out / path.name, data_only=True)["Summary"].iter_rows(values_only=True))
    for g, v in truth.items():
        row = next((r for r in grid if any(isinstance(c, str) and c.strip().lower() == g.lower() for c in r)), [])
        checks.append({"id": f"{g.lower()}_total", "pass": any(isinstance(c, (int, float)) and abs(c - v) < 0.01 for c in row), "detail": f"want {v}"})
    tot = next((r for r in grid if r and isinstance(r[0], str) and r[0].strip().lower().startswith("total")), [])
    checks.append({"id": "total_row", "pass": any(isinstance(c, (int, float)) and abs(c - sum(truth.values())) < 0.01 for c in tot), "detail": str(tot)})
    return _result(checks)


# ---- eval2: Excel with quantity times price per group ---------------------------------------------------
def excel_products(path, csv_path, group_col, qty_col, price_col):
    """Per group: total quantity and total of quantity x price; a Total row; formulas that refer to the Data sheet;
    checked after a real spreadsheet application recalculates the workbook."""
    from openpyxl import load_workbook
    path = Path(path)
    if not path.exists():
        return _result([{"id": "file_exists", "pass": False, "detail": str(path)}])
    rows = list(csv.DictReader(open(csv_path)))
    truth = {}
    for r in rows:
        t = truth.setdefault(r[group_col], [0.0, 0.0])
        t[0] += float(r[qty_col])
        t[1] += float(r[qty_col]) * float(r[price_col])
    grand = sum(v[1] for v in truth.values())
    checks = []
    wb = load_workbook(path)
    checks.append({"id": "has_data_and_summary_sheets", "pass": {"Data", "Summary"} <= set(wb.sheetnames), "detail": str(wb.sheetnames)})
    if "Data" in wb.sheetnames:
        n = sum(1 for row in wb["Data"].iter_rows(min_row=2, values_only=True) if any(v is not None for v in row))
        checks.append({"id": "data_sheet_has_all_rows", "pass": n == len(rows), "detail": f"{n} of {len(rows)}"})
    formulas = [c.value for row in (wb["Summary"].iter_rows() if "Summary" in wb.sheetnames else []) for c in row
                if isinstance(c.value, str) and c.value.startswith("=")]
    checks.append({"id": "summary_uses_formulas", "pass": len(formulas) >= len(truth) * 2, "detail": f"{len(formulas)} formulas"})
    checks.append({"id": "formulas_refer_to_data_sheet", "pass": any("Data" in f for f in formulas), "detail": formulas[:3]})
    out = Path(tempfile.mkdtemp(prefix="recalc-"))
    r = _soffice(["--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", str(out), str(path)])
    recalced = out / path.name
    if not recalced.exists():
        checks.append({"id": "recalculates_in_spreadsheet_app", "pass": False, "detail": (r.stderr or r.stdout)[-300:]})
        return _result(checks)
    vals = load_workbook(recalced, data_only=True)
    s = vals["Summary"] if "Summary" in vals.sheetnames else None
    errors = [c.value for row in (s.iter_rows() if s else []) for c in row if isinstance(c.value, str) and c.value.startswith("#")]
    checks.append({"id": "no_formula_errors", "pass": s is not None and not errors, "detail": errors[:3]})
    grid = [list(row) for row in s.iter_rows(values_only=True)] if s else []
    for g, (qty, money) in sorted(truth.items()):
        row = next((r for r in grid if any(isinstance(c, str) and c.strip().lower() == g.lower() for c in r)), None)
        nums = [c for c in (row or []) if isinstance(c, (int, float))]
        checks.append({"id": f"{g.lower()}_totals_correct", "pass": any(abs(n - qty) < 0.01 for n in nums) and any(abs(n - money) < 0.01 for n in nums),
                       "detail": f"want {qty:g} and {money:.2f}; row {row}"})
    total_row = next((r for r in grid if r and isinstance(r[0], str) and r[0].strip().lower().startswith("total")), None)
    checks.append({"id": "total_row_correct", "pass": bool(total_row) and any(isinstance(c, (int, float)) and abs(c - grand) < 0.01 for c in total_row),
                   "detail": f"want {grand:.2f}; row {total_row}"})
    shutil.rmtree(out, ignore_errors=True)
    return _result(checks)
