#!/bin/bash
# All counted core-proof runs, in this order: 2 GB run 1, 4 GB run 1, 2 GB run 2, 4 GB run 2, 2 GB run 3, 4 GB run 3.
# Resumable: start it again after a restart and it skips every task already recorded.
cd "$(dirname "$0")/../.." || exit 1
for k in 1 2 3; do
  for tier in 2gb 4gb; do
    python3 -m benchmark.proof.run --tier "$tier" --run "$k" || echo "RUN FAILED $tier $k"
  done
done
echo ALL-PROOF-RUNS-DONE
