#!/usr/bin/env bash
# Model selection on the dev set, FULL condition, each candidate inside its tier. Resumable.
cd "$(dirname "$0")/.."
run() { python3 -m benchmark.harness --set dev --tier "$1" --condition full --model "$2" --tag "sel-$2"; }
run 2gb qwen3.5-0.8b-q8
run 4gb qwen2.5-coder-3b-q4
run 4gb qwen3.5-4b-q4
run 8gb qwen2.5-coder-7b-q4
run 8gb qwen3.5-9b-q4
echo SELECTION-DONE
