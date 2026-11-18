#!/usr/bin/env bash
# NEURON installer for Linux (tested on Ubuntu 24.04). Run from the repository folder:
#   bash scripts/install.sh            install, self-test, then start NEURON
#   bash scripts/install.sh --no-start install and self-test only
#   bash scripts/install.sh --plan     show the memory tier and model it would pick, change nothing
# Options after these are passed to the Python installer (for example --tier 4gb).
# Needs the internet once (system packages, Python libraries, llama.cpp source, the model).
# llama.cpp is built without its web UI and never downloads UI files (NEURON has its own phone page; the UI
# download comes from a bucket that changes over time and broke a clean build on 2026-11-18).
# After that NEURON works offline.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
NEURON_HOME="${NEURON_HOME:-$HOME/.neuron}"
START=1; PLAN=0; ARGS=()
for a in "$@"; do
  case "$a" in --no-start) START=0 ;; --plan) PLAN=1; ARGS+=("--plan") ;; *) ARGS+=("$a") ;; esac
done
say() { printf '\n== %s\n' "$*"; }

[ "$(uname -s)" = "Linux" ] || { echo "This installer is for Linux. Windows and Mac are not supported yet."; exit 1; }
if [ "$PLAN" = 1 ]; then cd "$REPO" && exec python3 -m neuron.install --home "$NEURON_HOME" "${ARGS[@]}"; fi

SUDO=""; [ "$(id -u)" = 0 ] || SUDO="sudo"
say "System packages"
if command -v apt-get >/dev/null; then
  PKGS="python3 python3-venv python3-pip bubblewrap curl ca-certificates cmake build-essential git"
  OFFICE="libreoffice-calc libreoffice-writer libreoffice-impress"   # used to check spreadsheets, documents and slides
  missing=""
  for p in $PKGS $OFFICE; do dpkg -s "$p" >/dev/null 2>&1 || missing="$missing $p"; done
  if [ -n "$missing" ]; then $SUDO apt-get update -q && $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends $missing; fi
  echo "ok"
else
  echo "No apt-get here. Install these yourself, then run this again: python3 (3.11+), venv, bubblewrap, cmake, a C++ compiler, libreoffice."
  for c in python3 bwrap cmake c++; do command -v $c >/dev/null || { echo "missing: $c"; exit 1; }; done
fi

say "Python libraries (private copy in $NEURON_HOME/venv)"
mkdir -p "$NEURON_HOME"
[ -x "$NEURON_HOME/venv/bin/python" ] || python3 -m venv "$NEURON_HOME/venv"
"$NEURON_HOME/venv/bin/pip" install -q --disable-pip-version-check -r "$REPO/requirements.txt"
PY="$NEURON_HOME/venv/bin/python"; echo "ok"

say "llama.cpp (the program that runs the model on this computer's processor)"
LLAMA="${NEURON_LLAMA_DIR:-$NEURON_HOME/llama}"
if [ -n "${NEURON_LLAMA_BIN:-}" ] && [ -x "$NEURON_LLAMA_BIN" ]; then
  BIN="$NEURON_LLAMA_BIN"; echo "using $BIN"
else
  BIN="$LLAMA/build/bin/llama-server"
  if [ ! -x "$BIN" ]; then
    mkdir -p "$LLAMA/sdist"
    "$NEURON_HOME/venv/bin/pip" download -q --no-deps --no-binary :all: llama-cpp-python==0.3.36 -d "$LLAMA/sdist"
    tar xzf "$LLAMA/sdist/llama_cpp_python-0.3.36.tar.gz" -C "$LLAMA/sdist"
    cmake -S "$LLAMA/sdist/llama_cpp_python-0.3.36/vendor/llama.cpp" -B "$LLAMA/build" -DCMAKE_BUILD_TYPE=Release \
      -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_SERVER=ON -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF \
      -DLLAMA_OPENSSL=OFF -DGGML_NATIVE=ON -DBUILD_SHARED_LIBS=OFF > "$LLAMA/cmake.log"
    cmake --build "$LLAMA/build" --target llama-server -j"$(nproc)" > "$LLAMA/build.log"
  fi
  echo "ok: $BIN"
fi

say "Memory, model, checksum and self-test"
cd "$REPO"
set +e
"$PY" -m neuron.install --home "$NEURON_HOME" --llama-bin "$BIN" "${ARGS[@]}"
code=$?
set -e
[ $code = 0 ] || { echo "The installer reported a problem (code $code). NEURON was not started."; exit $code; }

cat > "$NEURON_HOME/start.sh" <<EOS
#!/usr/bin/env bash
cd "$REPO" && exec "$PY" -m neuron.server --home "$NEURON_HOME" "\$@"
EOS
chmod +x "$NEURON_HOME/start.sh"
if command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; then
  mkdir -p "$HOME/.config/systemd/user"
  cat > "$HOME/.config/systemd/user/neuron.service" <<EOS
[Unit]
Description=NEURON
[Service]
ExecStart=$NEURON_HOME/start.sh
Restart=on-failure
[Install]
WantedBy=default.target
EOS
  systemctl --user daemon-reload
  echo "Start on login: systemctl --user enable --now neuron"
fi
echo "Start any time: $NEURON_HOME/start.sh   New pairing code (while it runs): $NEURON_HOME/start.sh code"
if [ "$START" = 1 ]; then say "Starting NEURON"; exec "$NEURON_HOME/start.sh"; fi
