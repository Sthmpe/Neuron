#!/usr/bin/env bash
# Sets up the local model for NEURON: builds llama.cpp (CPU only) and downloads the model.
# These are the steps that were used on the development machine.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LLAMA_DIR="${LLAMA_DIR:-$REPO/../llama}"     # next to the repo; the brain looks here first
MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-1.5b-instruct-q6_k.gguf"

# 1. llama.cpp source. github.com was not reachable from the build machine, so the source is
#    taken from the llama-cpp-python package on PyPI, which bundles the full llama.cpp tree.
mkdir -p "$LLAMA_DIR" && cd "$LLAMA_DIR"
if [ ! -x build/bin/llama-server ]; then
  pip download --no-deps --no-binary :all: llama-cpp-python==0.3.36 -d sdist
  tar xzf sdist/llama_cpp_python-0.3.36.tar.gz -C sdist
  cmake -S sdist/llama_cpp_python-0.3.36/vendor/llama.cpp -B build -DCMAKE_BUILD_TYPE=Release \
    -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_SERVER=ON -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF \
    -DLLAMA_OPENSSL=OFF -DGGML_NATIVE=ON -DBUILD_SHARED_LIBS=OFF
  cmake --build build --target llama-server -j"$(nproc)"
fi

# 2. sandbox tool
command -v bwrap >/dev/null || (apt-get update && apt-get install -y bubblewrap)

# 3. the model (1.46 GB). Needs huggingface.co and its download server us.aws.cdn.hf.co to be reachable.
#    sha256 9b05dce8089197c866b9f76e1db45de8617cda98d9d06059958cb8ad32c56dfa
mkdir -p "$REPO/models"
if ! ls "$REPO"/models/*.gguf >/dev/null 2>&1; then
  curl -fL --retry 3 -o "$REPO/models/$(basename "$MODEL_URL").part" "$MODEL_URL"
  mv "$REPO/models/$(basename "$MODEL_URL").part" "$REPO/models/$(basename "$MODEL_URL")"
fi
ls -la "$REPO/models"
