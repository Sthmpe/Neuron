#!/usr/bin/env bash
# Labelled rerun (not the step-3 score): the 3 held-out app builds with the system as it runs now
# (design system, template fallback, code-written database file, links and rules). Resumable.
cd "$(dirname "$0")/.."
for tier in 2gb 4gb 8gb; do
  python3 -m benchmark.harness --set heldout --tier $tier --condition full --kind builds --system current --tag rerun-current2
done
echo BUILDS-CURRENT2-DONE
