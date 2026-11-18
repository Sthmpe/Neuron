#!/usr/bin/env bash
# Polite retry of the real photo fetch: one attempt every 20 minutes, at most 9 attempts, stops when photos were found.
cd "$(dirname "$0")/../.."
for i in 1 2 3 4 5 6 7 8 9; do
  python3 -m benchmark.online.images_demo > /dev/null 2>&1
  n=$(python3 -c "import json;print(json.load(open('benchmark/results/online_images_demo.json'))['online'].get('licensed',0))")
  echo "[$(date '+%F %T')] attempt $i: licensed photos $n" >> benchmark/online/images_retry.log
  [ "$n" -gt 0 ] && exit 0
  sleep 1200
done
