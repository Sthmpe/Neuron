"""Builds the compiled-language workspace bug tasks (locked phase-5 set). Each task = whole codebase + one bug."""
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRATCH = os.environ.get("NEURON_SCRATCH", "/tmp")
BUGS = {
    "cpp_inventory": [
        ("src/inventory.cpp",
         '    if (quantity > item.stock) throw OutOfStock(sku + ": only " + std::to_string(item.stock) + " left");\n    item.stock -= quantity;',
         '    item.stock -= quantity;\n    if (item.stock < 0) throw OutOfStock(sku + ": only " + std::to_string(item.stock + quantity) + " left");'),
        ("src/pricing.cpp", "if (total_units >= 10) return 5;", "if (total_units > 10) return 5;"),
        ("src/csv.cpp", "while (frac.size() < 2) frac += '0';", "while (frac.size() < 2) frac = '0' + frac;"),
    ],
    "go_ledger": [
        ("ledger/rates.go", "r.scaled[key(to, from)] = RoundDiv(Scale*Scale, rate)", "r.scaled[key(to, from)] = rate"),
        ("ledger/money.go", "if 2*abs(r) >= abs(b) {", "if 2*abs(r) > abs(b) {"),
    ],
}
TEST = {"cpp_inventory": ["make", "-s", "test"], "go_ledger": ["go", "test", "./..."]}


def passes(folder, ws):
    env = {**os.environ, "HOME": SCRATCH, "GOCACHE": os.path.join(SCRATCH, "gocache"), "GOFLAGS": "-mod=mod"}
    p = subprocess.run(TEST[ws], cwd=folder, capture_output=True, text=True, env=env)
    subprocess.run(["make", "-s", "clean"], cwd=folder, capture_output=True) if ws.startswith("cpp") else None
    return p.returncode == 0


def main():
    out, sol = HERE / "workspace_tasks", HERE / "workspace_solutions"
    shutil.rmtree(out, ignore_errors=True)
    shutil.rmtree(sol, ignore_errors=True)
    for ws, bugs in BUGS.items():
        assert passes(HERE / "workspaces" / ws, ws), f"clean {ws} fails"
        for i, (rel, good, bad) in enumerate(bugs):
            name = f"{ws}_bug{i}"
            dst = out / name
            shutil.copytree(HERE / "workspaces" / ws, dst)
            text = (dst / rel).read_text()
            assert text.count(good) == 1, (name, "snippet must appear exactly once")
            (dst / rel).write_text(text.replace(good, bad))
            assert not passes(dst, ws), f"{name}: the planted bug breaks no test"
            (sol / name / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(HERE / "workspaces" / ws / rel, sol / name / rel)
            print(f"{name}: bug in {rel} breaks the tests; fix restores them")


if __name__ == "__main__":
    main()
