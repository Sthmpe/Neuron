#!/usr/bin/env bash
# Second selection round (non-Qwen candidates, added at the owner's request). Same dev set, same rules.
cd "$(dirname "$0")/.."
until grep -q SELECTION-DONE benchmark/select.log; do sleep 60; done
until grep -q ALL-DONE models/download2.log; do sleep 30; done
# disk is tight: the 8 GB round-one loser cannot win any more (the winner already beat it), so its file is removed
python3 - <<'PY'
import json, subprocess
from pathlib import Path
def score(m):
    rows = json.loads(Path(f"benchmark/results/dev/8gb-full-sel-{m}.json").read_text())["rows"]
    return (sum(r["solved"] for r in rows if r["type"] == "bug") + sum(r["passed"] / r["total"] for r in rows if r["type"] == "build"),
            -sum(r["seconds"] for r in rows))
a, b = "qwen2.5-coder-7b-q4", "qwen3.5-9b-q4"
loser = a if score(a) < score(b) else b
f = json.loads(Path(f"model_manifests/{loser}.json").read_text())["file"]
subprocess.run(["python3", "-m", "neuron.brain.models", "remove", loser])
Path("models/store", f).unlink(missing_ok=True)
print("removed round-one 8 GB loser", loser)
PY
for m in gemma-4-e2b-q4 gemma-4-e4b-q4 granite-4.1-3b-q4 granite-4.1-8b-q4; do
  python3 -m neuron.brain.models install model_manifests/$m.json && python3 -m neuron.brain.models measure $m
done
python3 -m neuron.brain.models list
run() { python3 -m neuron.brain.models list | grep -q "^$2 .*fits:.*$1" && python3 -m benchmark.harness --set dev --tier "$1" --condition full --model "$2" --tag "sel-$2" || echo "SKIP $2 does not fit $1"; }
run 4gb gemma-4-e2b-q4
run 4gb granite-4.1-3b-q4
run 8gb gemma-4-e4b-q4
run 8gb granite-4.1-8b-q4
echo SELECTION2-DONE
