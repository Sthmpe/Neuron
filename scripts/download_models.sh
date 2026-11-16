#!/usr/bin/env bash
# Downloads every candidate model file BEFORE any offline benchmark run.
# Each file is checked against the sha256 that Hugging Face publishes for it.
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$REPO/models/store"; mkdir -p "$DEST"
FILES=(
  "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
  "unsloth/Qwen3.5-2B-GGUF Qwen3.5-2B-Q4_K_M.gguf"
  "Qwen/Qwen2.5-Coder-3B-Instruct-GGUF qwen2.5-coder-3b-instruct-q4_k_m.gguf"
  "unsloth/Qwen3.5-4B-GGUF Qwen3.5-4B-Q4_K_M.gguf"
  "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF qwen2.5-coder-7b-instruct-q4_k_m.gguf"
  "unsloth/Qwen3.5-9B-GGUF Qwen3.5-9B-Q4_K_M.gguf"
)
for entry in "${FILES[@]}"; do
  set -- $entry; repo=$1; file=$2; url="https://huggingface.co/$repo/resolve/main/$file"
  if [ -f "$DEST/$file" ]; then echo "have $file"; continue; fi
  want=$(curl -sS -I -m 60 "$url" | tr -d '\r' | awk -F'"' 'tolower($0) ~ /^x-linked-etag/ {print $2}')
  echo "downloading $file (expected sha256 ${want:-unknown})"
  if ! curl -fL --retry 5 --retry-delay 5 -C - -sS -o "$DEST/$file.part" "$url"; then echo "FAILED $file"; continue; fi
  got=$(sha256sum "$DEST/$file.part" | cut -d' ' -f1)
  if [ -n "$want" ] && [ "$want" != "$got" ]; then echo "CHECKSUM MISMATCH $file ($got)"; continue; fi
  mv "$DEST/$file.part" "$DEST/$file"; echo "$got  $file  $repo" >> "$DEST/SHA256SUMS"; echo "ok $file"
done
echo ALL-DONE
