"""Core proof, category D: document tasks (Excel, Word, PowerPoint, PDF answers). Examined with eval2's examiner functions
(imported, never modified). Inputs are generated deterministically by make_sources(). Written before any tuning."""
import csv
import random
from pathlib import Path

REGIONS = ["North", "South", "East", "West"]
PRODUCTS = [("Rice 50kg", 42000), ("Beans 25kg", 28000), ("Palm oil 5L", 9500), ("Sugar 1kg", 1800)]
DEPARTMENTS = ["Kitchen", "Cleaning", "Security"]
CATEGORIES = ["Transport", "Food", "Utilities", "Stationery"]

PDF_PAGES = [
    ("Riverside Community Clinic: Annual Report 2026", [
        "The clinic opened its second consulting room in March 2026.",
        "Adult patients seen during the year: 4,860. Children seen: 2,140.",
        "The clinic employs 6 nurses and 2 doctors.",
        "Opening hours are 8am to 6pm on weekdays and 9am to 1pm on Saturdays.",
        "The clinic is run by a board of 7 volunteer trustees."]),
    ("Services and fees", [
        "A general consultation costs 3,000 naira for adults and 1,500 naira for children.",
        "Antenatal check-ups are free for registered mothers.",
        "Blood tests cost 4,500 naira; malaria tests cost 1,200 naira.",
        "The clinic carried out 1,350 malaria tests and 610 blood tests in 2026.",
        "Home visits are offered within 5 kilometres of the clinic."]),
    ("Money and plans", [
        "Income in 2026 was 18.4 million naira, of which grants were 6.1 million naira.",
        "Spending was 16.9 million naira; staff costs were 9.8 million naira of that.",
        "The clinic plans a pharmacy corner in 2027 at an estimated cost of 2.3 million naira.",
        "A new generator bought in July 2026 cost 1.1 million naira.",
        "The board aims to see 8,000 patients in 2027."]),
]
PDF_QUESTIONS = [
    {"q": "How many children did the clinic see in 2026?", "expect": ["2140"], "doc": "riverside_clinic_report_2026", "page": 1},
    {"q": "How many nurses does the clinic employ?", "expect": ["6"], "doc": "riverside_clinic_report_2026", "page": 1},
    {"q": "How much does a general consultation cost for a child?", "expect": ["1500"], "doc": "riverside_clinic_report_2026", "page": 2},
    {"q": "How many blood tests did the clinic carry out in 2026?", "expect": ["610"], "doc": "riverside_clinic_report_2026", "page": 2},
    {"q": "How much were staff costs in 2026?", "expect": ["9.8"], "doc": "riverside_clinic_report_2026", "page": 3},
    {"q": "What is the estimated cost of the planned pharmacy corner?", "expect": ["2.3"], "doc": "riverside_clinic_report_2026", "page": 3},
]


def make_sources(src):
    src = Path(src)
    src.mkdir(parents=True, exist_ok=True)
    r = random.Random(20261120)
    with open(src / "regional_sales_2026.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["region", "product", "units", "unit_price"])
        for region in REGIONS:
            for name, price in PRODUCTS:
                w.writerow([region, name, r.randint(3, 40), price])
    with open(src / "staff_hours_october.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["department", "staff", "hours", "hourly_rate"])
        names = ["Ada", "Bayo", "Chika", "Dayo", "Efe", "Funmi", "Gbenga", "Hauwa", "Ike"]
        for i, n in enumerate(names):
            w.writerow([DEPARTMENTS[i % 3], n, r.randint(60, 180), r.choice([900, 1100, 1300])])
    with open(src / "office_expenses_q3.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "category", "amount"])
        for day in range(1, 21):
            w.writerow([f"2026-0{7 + day % 3}-{day:02d}", CATEGORIES[day % 4], r.randint(2, 60) * 500])
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(src / "riverside_clinic_report_2026.pdf"), pagesize=A4, invariant=1)
    for title, lines in PDF_PAGES:
        c.setFont("Helvetica-Bold", 16)
        c.drawString(60, 780, title)
        c.setFont("Helvetica", 11)
        y = 740
        for line in lines:
            c.drawString(60, y, line)
            y -= 24
        c.showPage()
    c.save()


DOCS = [
    {"id": "D1_excel_regional_sales", "kind": "excel_products", "inputs": ["sources/regional_sales_2026.csv"], "output": "sales_summary.xlsx",
     "args": ["region", "units", "unit_price"],
     "request": "Make sales_summary.xlsx from the attached CSV: put all the rows on a sheet named Data, and on a sheet named "
                "Summary show, for each region, the total units and the total revenue (units times unit price) using formulas, "
                "with a Total row at the bottom."},
    {"id": "D2_excel_staff_costs", "kind": "excel_products", "inputs": ["sources/staff_hours_october.csv"], "output": "staff_costs.xlsx",
     "args": ["department", "hours", "hourly_rate"],
     "request": "Make staff_costs.xlsx from the attached October hours: the rows on a sheet named Data, and a sheet named Summary "
                "with, for each department, the total hours and the total pay (hours times hourly rate) as formulas, plus a "
                "Total row."},
    {"id": "D3_excel_expenses", "kind": "excel_simple", "inputs": ["sources/office_expenses_q3.csv"], "output": "expenses_summary.xlsx",
     "args": ["category", "amount"],
     "request": "Make expenses_summary.xlsx from the attached third-quarter expenses: the rows on a sheet named Data and a sheet "
                "named Summary with the total amount for each category, using formulas, and a Total row."},
    {"id": "D4_word_repair_request", "kind": "word", "inputs": [], "output": "repair_request.docx",
     "word": {"headings": ["Problem", "What I am asking for", "Timeline"], "words": [150, 350],
              "table": {"header": ["Item", "Cost (NGN)"], "rows": {"Kitchen tap": 12000, "Bathroom door lock": 8500, "Window glass": 20000}}},
     "request": "Write repair_request.docx, a letter to my landlord asking for repairs in my flat, with the headings Problem, "
                "What I am asking for and Timeline, between 150 and 350 words. Include a table with the columns Item and Cost "
                "(NGN) listing Kitchen tap 12000, Bathroom door lock 8500 and Window glass 20000, and a Total row."},
    {"id": "D5_word_leave_policy", "kind": "word", "inputs": [], "output": "leave_policy.docx",
     "word": {"headings": ["Purpose", "Types of leave", "How to apply"], "words": [200, 400],
              "table": {"header": ["Leave type", "Days"], "rows": {"Annual": 20, "Sick": 10, "Compassionate": 5}}},
     "request": "Write leave_policy.docx for the staff of a small printing company, with the headings Purpose, Types of leave "
                "and How to apply, between 200 and 400 words. Include a table with the columns Leave type and Days: Annual 20, "
                "Sick 10, Compassionate 5, and a Total row."},
    {"id": "D6_pptx_cooperative_agm", "kind": "pptx", "inputs": [], "output": "agm_2026.pptx",
     "pptx": {"slides": 6, "must_contain": ["Unity Farmers", "12%"], "max_bullets": 5},
     "request": "Make agm_2026.pptx, a 6-slide deck for the annual general meeting of Unity Farmers Cooperative: welcome, the "
                "year in numbers (maize sales rose 12%), new members, the storage barn project, next year's plans, and "
                "questions. At most 5 bullet points on a slide."},
    {"id": "D7_pptx_fire_safety", "kind": "pptx", "inputs": [], "output": "fire_safety.pptx",
     "pptx": {"slides": 4, "must_contain": ["car park", "112"], "max_bullets": 5},
     "request": "Make fire_safety.pptx, a 4-slide training deck for shop staff on fire safety: preventing fires, using the "
                "extinguisher, what to do when the alarm sounds (meet at the assembly point in the car park), and calling the "
                "emergency number 112. At most 5 bullet points on a slide."},
    {"id": "D8_pdf_clinic_report", "kind": "pdf_qa", "inputs": ["sources/riverside_clinic_report_2026.pdf"], "output": "answers",
     "questions": PDF_QUESTIONS,
     "request": "Answer these questions from the attached clinic report, giving the page number for each answer:\n"
                + "\n".join(f"{i + 1}. {q['q']}" for i, q in enumerate(PDF_QUESTIONS))},
]

for d in DOCS:
    d["category"] = "document"
    d["budget_s"] = 480
