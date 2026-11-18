"""Each dev project: the shipped bug fails its tests, the reference fix passes them."""
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXES = {  # project: (file, old, new)
    "cpp_tickets": ("src/tickets.cpp", "if (age > 65) return 0;", "if (age >= 65) return 0;"),
    "cpp_grades": ("src/grades.cpp", "if (mark > 40) return 'D';", "if (mark >= 40) return 'D';"),
    "go_parking": ("parking/fee.go", "if minutes < 30 {", "if minutes <= 30 {"),
    "go_stock": ("stock/reorder.go", "return target + left", "return target - left"),
    "go_split": ("bill/split.go", "\treturn shares\n", "\tfor i := 0; i < totalKobo%people; i++ {\n\t\tshares[i]++\n\t}\n\treturn shares\n"),
    "cpp_trim": ("src/text.cpp", "find_first_not_of(' ')", 'find_first_not_of(" \\t\\r\\n")'),
}


def test_cmd(d):
    return ["go", "test", "./..."] if (d / "go.mod").exists() else ["make", "-s", "test"]


def main():
    ok = True
    for name in sorted(p.name for p in (HERE / "workspaces").iterdir()):
        for fixed in (False, True):
            d = Path(tempfile.mkdtemp()) / name
            shutil.copytree(HERE / "workspaces" / name, d)
            if fixed:
                if name not in FIXES:
                    continue
                f, old, new = FIXES[name]
                t = (d / f).read_text()
                assert old in t, (name, old)
                t = t.replace(old, new)
                if name == "cpp_trim":
                    t = t.replace("find_last_not_of(' ')", 'find_last_not_of(" \\t\\r\\n")')
                (d / f).write_text(t)
            r = subprocess.run(test_cmd(d), cwd=d, capture_output=True, text=True)
            good = (r.returncode == 0) == fixed
            ok &= good
            print(f"{'OK ' if good else 'BAD'} {name} {'reference fix' if fixed else 'as shipped'}: tests {'pass' if r.returncode == 0 else 'fail'}")
            shutil.rmtree(d.parent, ignore_errors=True)
    print("VALID" if ok else "INVALID")


if __name__ == "__main__":
    main()
