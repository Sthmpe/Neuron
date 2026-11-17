#!/usr/bin/env bash
# Runs unattended: wait for both selection rounds, choose winners by the written rule, run held-out scoring.
cd "$(dirname "$0")/.."
until grep -q SELECTION2-DONE benchmark/select2.log; do sleep 60; done
python3 benchmark/choose_winners.py > benchmark/choose.log 2>&1
benchmark/heldout_runs.sh > benchmark/heldout.log 2>&1
