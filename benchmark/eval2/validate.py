"""Validate every eval2 examiner before the lock: a correct reference must pass it, a wrong or empty delivery must fail it.

  python3 -m benchmark.eval2.validate
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.eval2.examine import examine          # noqa: E402

TASKS = {t["id"]: t for t in json.loads((HERE / "locked" / "tasks.json").read_text())}


def tmp():
    return Path(tempfile.mkdtemp(prefix="e2val-"))


def ref_excel(d):
    from openpyxl import Workbook
    import csv
    rows = list(csv.DictReader(open(HERE / "sources" / "clinic_visits_2026.csv")))
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(["date", "department", "visits", "fee_per_visit"])
    for r in rows:
        ws.append([r["date"], r["department"], int(r["visits"]), int(r["fee_per_visit"])])
    n = len(rows) + 1
    s = wb.create_sheet("Summary")
    s.append(["Department", "Visits", "Fees"])
    deps = sorted({r["department"] for r in rows})
    for i, dpt in enumerate(deps, 2):
        s.append([dpt, f'=SUMIF(Data!B2:B{n},A{i},Data!C2:C{n})', f'=SUMPRODUCT((Data!B2:B{n}=A{i})*Data!C2:C{n}*Data!D2:D{n})'])
    last = len(deps) + 1
    s.append(["Total", f"=SUM(B2:B{last})", f"=SUM(C2:C{last})"])
    wb.save(d / "clinic_summary.xlsx")


def ref_word(d):
    import docx
    doc = docx.Document()
    doc.add_heading("Rent review 2027", 0)
    body = ("Harbourview Apartments writes to every tenant about the rent review that takes effect in January 2027. "
            "This notice explains what changes, why it changes and what you need to do before the end of the year. ")
    for h in ("Purpose", "Details", "Next steps"):
        doc.add_heading(h, 1)
        doc.add_paragraph(body * 2)
    t = doc.add_table(rows=1, cols=2)
    t.rows[0].cells[0].text, t.rows[0].cells[1].text = "Item", "Amount (NGN)"
    for item, amt in (("Rent", "450000"), ("Service charge", "60000"), ("Caution deposit", "100000"), ("Total", "610000")):
        c = t.add_row().cells
        c[0].text, c[1].text = item, amt
    doc.save(d / "tenancy_notice.docx")


def ref_pptx(d):
    from pptx import Presentation
    prs = Presentation()
    for title, bullets in (("Food safety at Mama Put Kitchens", ["Training for kitchen staff"]),
                           ("Handwashing", ["Wash for 20 seconds", "Before and after handling raw meat"]),
                           ("Safe cooking temperatures", ["Cook chicken to 75 degrees Celsius", "Use a thermometer"]),
                           ("Storage", ["Cold food below 5 degrees", "Label and date"]), ("Cleaning", ["Clean as you go", "Sanitise boards"])):
        s = prs.slides.add_slide(prs.slide_layouts[1])
        s.shapes.title.text = title
        tf = s.placeholders[1].text_frame
        tf.text = bullets[0]
        for b in bullets[1:]:
            tf.add_paragraph().text = b
    prs.save(d / "food_safety.pptx")


CSVSUM_CPP = r'''#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
static std::vector<std::string> split(const std::string& s) {
    std::vector<std::string> out; std::string cell; std::stringstream ss(s);
    while (std::getline(ss, cell, ',')) { size_t a = cell.find_first_not_of(" \t\r"), b = cell.find_last_not_of(" \t\r");
        out.push_back(a == std::string::npos ? "" : cell.substr(a, b - a + 1)); }
    return out;
}
static bool num(const std::string& s, double& v) { try { size_t k; v = std::stod(s, &k); return k == s.size(); } catch (...) { return false; } }
int main(int argc, char** argv) {
    if (argc < 2) return 1;
    std::ifstream f(argv[1]); std::string line; std::getline(f, line);
    auto head = split(line); std::vector<double> tot(head.size(), 0); std::vector<bool> ok(head.size(), true);
    while (std::getline(f, line)) { if (line.find_first_not_of(" \t\r") == std::string::npos) continue;
        auto c = split(line); for (size_t i = 0; i < head.size(); ++i) { double v; if (i < c.size() && num(c[i], v)) tot[i] += v; else ok[i] = false; } }
    std::cout << std::fixed << std::setprecision(2);
    for (size_t i = 0; i < head.size(); ++i) if (ok[i]) std::cout << head[i] << ": " << tot[i] << "\n";
}
'''


def ref_csvsum(d):
    (d / "src").mkdir()
    (d / "src" / "main.cpp").write_text(CSVSUM_CPP)
    (d / "Makefile").write_text("csvsum: src/main.cpp\n\tg++ -std=c++17 -O2 -o csvsum src/main.cpp\n")


def ref_docstrings(d):
    import ast
    shutil.copytree(HERE / "workspaces" / "pantry_docs", d, dirs_exist_ok=True)
    for f in d.rglob("*.py"):
        if "tests" in f.parts:
            continue
        lines = f.read_text().splitlines()
        tree = ast.parse("\n".join(lines))
        fns = sorted((n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))), key=lambda n: -n.lineno)
        for n in fns:
            indent = " " * n.body[0].col_offset
            lines.insert(n.body[0].lineno - 1, f'{indent}"""{n.name.replace("_", " ").capitalize()}: works on the pantry items and returns the result."""')
        f.write_text("\n".join(lines) + "\n")


REPAIR_SCHEMA = '''def setup(app):
    app.db.execute("CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY, name TEXT, phone TEXT)")
    app.db.execute("CREATE TABLE IF NOT EXISTS repairs(id INTEGER PRIMARY KEY, customer TEXT, device TEXT, parts REAL, labour REAL)")
    app.add_user("tunde", "spanner9")
    app.enable_login()
    app.nav = [("Dashboard", "/"), ("Customers", "/customers"), ("Repairs", "/repairs")]
'''
REPAIR_PAGES = {
    "dashboard.py": '''from kit import ui


def register(app):
    @app.route("/", login=True)
    def dashboard(req):
        billed = app.db.value("SELECT COALESCE(SUM(parts + labour), 0) FROM repairs")
        return app.page(req, "Dashboard", ui.stats(ui.stat("Customers", app.db.value("SELECT COUNT(*) FROM customers")),
                                                   ui.stat("Repairs", app.db.value("SELECT COUNT(*) FROM repairs")),
                                                   ui.stat("Total billed", format(billed, "g"))))
''',
    "customers.py": '''from kit.web import redirect
from kit import ui


def register(app):
    @app.route("/customers", methods=["GET", "POST"], login=True)
    def customers(req):
        if req.method == "POST":
            app.db.execute("INSERT INTO customers(name, phone) VALUES(?, ?)", [req.form.get("name", ""), req.form.get("phone", "")])
            return redirect("/customers")
        rows = [[r["name"], r["phone"]] for r in app.db.query("SELECT * FROM customers ORDER BY id DESC")]
        return app.page(req, "Customers", ui.table(["Name", "Phone"], rows),
                        ui.card("Add customer", ui.form("/customers", ui.field("Name", "name"), ui.field("Phone", "phone", type="tel"), submit="Add")))
''',
    "repairs.py": '''from kit.web import redirect
from kit import ui


def register(app):
    @app.route("/repairs", methods=["GET", "POST"], login=True)
    def repairs(req):
        if req.method == "POST":
            app.db.execute("INSERT INTO repairs(customer, device, parts, labour) VALUES(?, ?, ?, ?)",
                           [req.form.get("customer", ""), req.form.get("device", ""), float(req.form.get("parts") or 0), float(req.form.get("labour") or 0)])
            return redirect("/repairs")
        rows = [[r["customer"], r["device"], format(r["parts"], "g"), format(r["labour"], "g"), format(r["parts"] + r["labour"], "g")]
                for r in app.db.query("SELECT * FROM repairs ORDER BY id DESC")]
        names = [r["name"] for r in app.db.query("SELECT name FROM customers ORDER BY name")]
        return app.page(req, "Repairs", ui.table(["Customer", "Device", "Parts", "Labour", "Total"], rows),
                        ui.card("Add repair", ui.form("/repairs", ui.select("Customer", "customer", names), ui.field("Device", "device"),
                                                      ui.field("Parts cost", "parts", type="number"), ui.field("Labour cost", "labour", type="number"), submit="Add")))
''',
}


def ref_app(d):
    from neuron.builder.build import prepare_project
    app = d / "app"
    prepare_project(app, "Tunde Fixes", design=True)
    (app / "schema.py").write_text(REPAIR_SCHEMA)
    for name, code in REPAIR_PAGES.items():
        (app / "pages" / name).write_text(code)


def main():
    results = {}

    def expect(tid, delivered, should_pass, label, answers=None):
        r = examine(TASKS[tid], delivered, answers=answers, out_dir=tmp())
        ok = (r["passed"] == r["total"] and r["total"] > 0) == should_pass
        results[f"{tid} {label}"] = {"as_expected": ok, "score": f"{r['passed']}/{r['total']}",
                                     "failed": [c["id"] for c in r["checks"] if not c["pass"]][:6]}
        print(f"{'OK  ' if ok else 'BAD '} {tid} {label}: {r['passed']}/{r['total']}", flush=True)

    good_pdf = [f"{q['expect'][0]} (harbour market report 2026, page {q['page']})" for q in TASKS["E01_pdf_market"]["questions"]]
    good_pdf[4] = "12 tonnes (harbour market report 2026, page 3)"
    expect("E01_pdf_market", tmp(), True, "correct answers", good_pdf)
    expect("E01_pdf_market", tmp(), False, "wrong pages", [a.replace("page", "page 9 not") for a in good_pdf])
    d = tmp(); ref_excel(d); expect("E02_excel_clinic", d, True, "reference workbook")
    expect("E02_excel_clinic", tmp(), False, "nothing delivered")
    d = tmp(); ref_word(d); expect("E03_word_notice", d, True, "reference document")
    expect("E03_word_notice", tmp(), False, "nothing delivered")
    d = tmp(); ref_pptx(d); expect("E04_pptx_training", d, True, "reference deck")
    expect("E04_pptx_training", tmp(), False, "nothing delivered")
    for tid, ws in (("E05_python_bug", "pantry"), ("E06_js_bug", "invoice_js"), ("E07_go_bug", "go_shifts"), ("E08_rust_bug", "rust_temps")):
        expect(tid, HERE / "workspaces" / ws, True, "reference fix")
        expect(tid, HERE / "workspace_tasks" / f"{ws}_bug", False, "bug as shipped")
    d = tmp(); ref_csvsum(d); expect("E09_cpp_csvsum", d, True, "reference program")
    expect("E09_cpp_csvsum", tmp(), False, "nothing delivered")
    d = tmp(); ref_app(d); expect("E10_repair_app", d / "app", True, "reference app")
    expect("E10_repair_app", tmp(), False, "nothing delivered")
    d = tmp() / "p"; ref_docstrings(d); expect("E11_long_docstrings", d, True, "reference docstrings")
    expect("E11_long_docstrings", HERE / "workspaces" / "pantry_docs", False, "no docstrings added")
    d = tmp(); (d / "answer.md").write_text("She pays 46,010 naira in total.\n"); expect("E12_computed_answer", d, True, "right number")
    d = tmp(); (d / "answer.md").write_text("She pays 42,800 naira.\n"); expect("E12_computed_answer", d, False, "VAT forgotten")
    (HERE / "validation.json").write_text(json.dumps(results, indent=1))
    bad = [k for k, v in results.items() if not v["as_expected"]]
    print("VALIDATION", "PASSED" if not bad else f"FAILED: {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
