"""Builds the workspace bug tasks: each task is a whole codebase with ONE planted bug.
The clean codebases live next to this file; the reference fix of each task is the clean file."""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUGS = [
    ("w01_vat_rounding", "shopkeeper", "shopkeeper/services/pricing.py",
     "return int(amount * VAT_PERCENT / 100 + 0.5)", "return int(amount * VAT_PERCENT / 100)"),
    ("w02_order_rollback", "shopkeeper", "shopkeeper/services/orders.py",
     "            for sku, quantity in reserved:\n                self.inventory.release(sku, quantity)\n            raise", "            raise"),
    ("w03_due_date_weekend", "shopkeeper", "shopkeeper/services/invoices.py",
     "return next_working_day(add_days(order_date, TERMS_DAYS))", "return add_days(order_date, TERMS_DAYS)"),
    ("w04_cancelled_spelling", "shopkeeper", "shopkeeper/services/reports.py",
     'if order.status == "cancelled":', 'if order.status == "canceled":'),
    ("w05_search_case", "shopkeeper", "shopkeeper/storage/repository.py",
     "if text in p.name.lower()", "if text in p.name"),
    ("w06_lunch_slots", "clinic", "clinic/scheduling/slots.py",
     "if not overlaps(t, t + length, lunch_start, lunch_end):", "if not (lunch_start < t < lunch_end):"),
    ("w07_cancelled_blocks", "clinic", "clinic/scheduling/book.py",
     ' and a.status != "cancelled"]', "]"),
    ("w08_reminder_day", "clinic", "clinic/scheduling/reminders.py",
     "day_before(a.date) != today", "a.date != today"),
    ("w09_insurance_share", "clinic", "clinic/billing/fees.py",
     "return fee - fee * INSURANCE_SHARE // 100", "return fee * INSURANCE_SHARE // 100"),
    ("w10_child_age", "clinic", "clinic/core/people.py",
     "return self.age_in(year) < 16", "return self.age_in(year) <= 16"),
]


def tests_pass(folder):
    p = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=folder,
                       capture_output=True, text=True)
    return p.returncode == 0, p.stderr.strip().splitlines()[-1] if p.stderr.strip() else ""


def main():
    out, sol = HERE / "tasks", HERE / "task_solutions"
    shutil.rmtree(out, ignore_errors=True)
    shutil.rmtree(sol, ignore_errors=True)
    for base in ("shopkeeper", "clinic"):
        ok, msg = tests_pass(HERE / base)
        assert ok, f"clean {base} fails: {msg}"
    for name, base, rel, good, bad in BUGS:
        dst = out / name
        shutil.copytree(HERE / base, dst, ignore=shutil.ignore_patterns("__pycache__"))
        text = (dst / rel).read_text()
        assert text.count(good) == 1, (name, "the clean snippet must appear exactly once")
        (dst / rel).write_text(text.replace(good, bad))
        ok, msg = tests_pass(dst)
        assert not ok, f"{name}: the planted bug breaks no test"
        (sol / name / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(HERE / base / rel, sol / name / rel)
        files = len(list(dst.rglob("*.py")))
        print(f"{name}: {files} python files, bug in {rel}: {msg}")


if __name__ == "__main__":
    main()
