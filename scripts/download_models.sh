#!/usr/bin/env bash
# Downloads every candidate model file BEFORE any offline benchmark run.
# Each file is checked against the sha256 that Hugging Face publishes for it.
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$REPO/models/store"; mkdir -p "$DEST"
FILES=(
  "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
  "unsloth/Qwen3.5-2B-GGUF Qwen3.5-2B-Q4_K_M.gguf"
  "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF qwen2.5-coder-1.5b-instruct-q5_k_m.gguf"
  "unsloth/Qwen3.5-0.8B-GGUF Qwen3.5-0.8B-Q8_0.gguf"
  "Qwen/Qwen2.5-Coder-3B-Instruct-GGUF qwen2.5-coder-3b-instruct-q4_k_m.gguf"
  "unsloth/Qwen3.5-4B-GGUF Qwen3.5-4B-Q4_K_M.gguf"
  "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF qwen2.5-coder-7b-instruct-q4_k_m.gguf"
  "unsloth/Qwen3.5-9B-GGUF Qwen3.5-9B-Q4_K_M.gguf"
  "unsloth/gemma-4-E2B-it-GGUF gemma-4-E2B-it-Q4_K_M.gguf"
  "unsloth/gemma-4-E4B-it-GGUF gemma-4-E4B-it-Q4_K_M.gguf"
  "unsloth/granite-4.1-3b-GGUF granite-4.1-3b-Q4_K_M.gguf"
  "unsloth/granite-4.1-8b-GGUF granite-4.1-8b-Q4_K_M.gguf"
)
ONLY=("$@")      # optional: only these file names (so deliberately removed models are not fetched again)
for entry in "${FILES[@]}"; do
  set -- $entry; repo=$1; file=$2; url="https://huggingface.co/$repo/resolve/main/$file"
  if [ ${#ONLY[@]} -gt 0 ] && [[ ! " ${ONLY[*]} " == *" $file "* ]]; then continue; fi
  if [ -f "$DEST/$file" ]; then echo "have $file"; continue; fi
  want=$(curl -sS -I -m 60 "$url" | tr -d '\r' | awk -F'"' 'tolower($0) ~ /^x-linked-etag/ {print $2}')
  echo "downloading $file (expected sha256 ${want:-unknown})"
  ok=0
  for try in 1 2 3 4 5 6 7 8 9 10; do   # the download server sometimes answers 429 (rate limit): wait and resume
    if curl -fL -C - -sS -m 3000 -o "$DEST/$file.part" "$url"; then ok=1; break; fi
    echo "  try $try failed, waiting 45s"; sleep 45
  done
  if [ $ok != 1 ]; then echo "FAILED $file"; continue; fi
  got=$(sha256sum "$DEST/$file.part" | cut -d' ' -f1)
  if [ -n "$want" ] && [ "$want" != "$got" ]; then echo "CHECKSUM MISMATCH $file ($got)"; continue; fi
  mv "$DEST/$file.part" "$DEST/$file"; echo "$got  $file  $repo" >> "$DEST/SHA256SUMS"; echo "ok $file"
done
echo ALL-DONE
