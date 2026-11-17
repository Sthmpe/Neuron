#!/usr/bin/env bash
# Second selection round (non-Qwen candidates, added at the owner's request). Same dev set, same rules.
cd "$(dirname "$0")/.."
until grep -q SELECTION-DONE benchmark/select.log; do sleep 60; done
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
