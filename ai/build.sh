#!/usr/bin/env bash
set -euo pipefail

# ==============================================================
# AI Service Build Script
#
# Purpose:
#   tokenizers (dep of chromadb) requires Rust compilation when
#   no pre-built wheel exists. Render's Python 3.14 build image
#   has /usr/local/cargo as read-only, so we install Rust into
#   a writable location before pip install.
# ==============================================================

# Use /opt/render/project which is writable during builds
CARGO_HOME="${CARGO_HOME:-/opt/render/project/.cargo}"
RUSTUP_HOME="${RUSTUP_HOME:-/opt/render/project/.rustup}"
TOOLCHAIN_DIR="${CARGO_HOME}/bin"

export CARGO_HOME
export RUSTUP_HOME
export PATH="${TOOLCHAIN_DIR}:${PATH}"

mkdir -p "${CARGO_HOME}" "${RUSTUP_HOME}"

# Install Rust toolchain only if not already present
if ! command -v cargo &>/dev/null; then
    echo ">>> Installing Rust toolchain (CARGO_HOME=${CARGO_HOME})..."
    curl -fsSL https://sh.rustup.rs \
        | sh -s -- -y \
            --default-toolchain stable \
            --no-modify-path \
            --profile minimal \
            2>&1
    echo ">>> Rust installed successfully."
fi

echo ">>> Installing Python dependencies..."
CARGO_HOME="${CARGO_HOME}" \
RUSTUP_HOME="${RUSTUP_HOME}" \
PATH="${TOOLCHAIN_DIR}:${PATH}" \
    pip install --no-cache-dir -r requirements.txt

echo ">>> Build complete."
