#!/bin/bash
# Labelled reruns AFTER the post-run fixes (informed by these same locked tasks, so expect them to overstate the
# general gain): NEURON only, same tasks, tiers, seeds and budgets as the counted runs. Resumable.
cd "$(dirname "$0")/../.." || exit 1
for k in 1 2 3; do
  for tier in 2gb 4gb; do
    python3 -m benchmark.proof.run --tier "$tier" --run "$k" --conditions neuron --tag after-fixes || echo "RUN FAILED $tier $k"
  done
done
echo ALL-AFTER-FIXES-DONE
