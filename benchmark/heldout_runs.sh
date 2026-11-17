#!/usr/bin/env bash
# Held-out scoring, step 3: every tier, both conditions, with the model chosen on the dev set. Resumable.
cd "$(dirname "$0")/.."
for tier in 2gb 4gb 8gb; do
  for cond in base full; do
    python3 -m benchmark.harness --set heldout --tier $tier --condition $cond
    python3 -m benchmark.harness --set workspace --tier $tier --condition $cond
  done
done
echo HELDOUT-DONE
