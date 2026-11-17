#!/usr/bin/env bash
# Resume selection after two harness problems (see PROGRESS): Qwen3.5-9B first-load timeout, Gemma thinking mode.
cd "$(dirname "$0")/.."
scripts/download_models.sh Qwen3.5-9B-Q4_K_M.gguf > models/download3.log 2>&1
python3 -m neuron.brain.models install model_manifests/qwen3.5-9b-q4.json
python3 -m benchmark.harness --set dev --tier 8gb --condition full --model qwen3.5-9b-q4 --tag sel-qwen3.5-9b-q4 --only 01_shopping_cart
for m in gemma-4-e2b-q4 gemma-4-e4b-q4; do python3 -m neuron.brain.models measure $m; done
run() { python3 -m neuron.brain.models list | grep -q "^$2 .*fits:.*$1" && python3 -m benchmark.harness --set dev --tier "$1" --condition full --model "$2" --tag "sel-$2" || echo "SKIP $2 does not fit $1"; }
run 4gb gemma-4-e2b-q4
run 4gb granite-4.1-3b-q4
run 8gb gemma-4-e4b-q4
run 8gb granite-4.1-8b-q4
echo SELECTION2-DONE >> benchmark/select2.log
