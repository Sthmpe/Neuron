#!/usr/bin/env bash
# All scorecard runs, resumable. Same fixed samples for every model and condition.
cd "$(dirname "$0")/../.."
for tier in 2gb 4gb 8gb; do
  for cond in alone neuron; do
    python3 -m benchmark.scorecard.run --tier $tier --condition $cond
  done
done
echo SCORECARD-ALL-DONE
