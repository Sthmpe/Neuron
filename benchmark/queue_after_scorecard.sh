#!/usr/bin/env bash
# Step 5 measurements, one model run at a time, started when the scorecard chain has finished (so no timings overlap).
# Resumable: each runner skips what it has already recorded. Order: the locked eval2 set on every tier (the honesty
# measurement), then the dev measurements (C++/Go repair with the small-change search on and off, computed totals).
cd "$(dirname "$0")/.."
until grep -q "SCORECARD-ALL-DONE" benchmark/scorecard.log; do sleep 300; done
log=benchmark/queue.log
echo "[$(date '+%F %T')] scorecard finished; starting step-5 measurements" >> $log
python3 benchmark/eval2/verify_lock.py >> $log 2>&1 || { echo "eval2 lock check FAILED; stopping" >> $log; exit 1; }
for tier in 2gb 4gb 8gb; do
  python3 -m benchmark.phase5.run --suite eval2 --set locked --tier $tier >> $log 2>&1
  echo "[$(date '+%F %T')] eval2 $tier finished" >> $log
done
for tier in 2gb 4gb 8gb; do
  python3 -m benchmark.repair_dev.run --tier $tier >> $log 2>&1
  NEURON_REPAIR_SEARCH=0 python3 -m benchmark.repair_dev.run --tier $tier --tag no-search >> $log 2>&1
  python3 -m benchmark.totals_dev.run --tier $tier >> $log 2>&1
  echo "[$(date '+%F %T')] dev measurements $tier finished" >> $log
done
echo "QUEUE-DONE" >> $log
