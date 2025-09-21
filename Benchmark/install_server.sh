#!/usr/bin/env bash
set -euo pipefail

which_cmd() {
  command -v "$1" >/dev/null 2>&1
}

install_linux_dependencies() {
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y \
      curl \
      python3 python3-venv python3-pip \
      openjdk-21-jdk \
      maven \
      golang-go \
      cargo
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y \
      curl \
      python3 python3-pip \
      java-21-openjdk java-21-openjdk-devel \
      maven \
      golang \
      rust cargo
  elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y \
      curl \
      python3 python3-pip \
      java-21-openjdk java-21-openjdk-devel \
      maven \
      golang \
      rust cargo
  else
    echo "Unsupported Linux distribution. Install curl, Python 3, OpenJDK 21, Maven, Go, and Rust manually." >&2
    exit 1
  fi
}

link_macos_jdk() {
  local target="/Library/Java/JavaVirtualMachines/openjdk-21.jdk"
  local source="$(brew --prefix)/opt/openjdk@21/libexec/openjdk.jdk"
  if [ -d "$source" ]; then
    sudo mkdir -p "/Library/Java/JavaVirtualMachines"
    sudo ln -sfn "$source" "$target"
  fi
}

case "$(uname -s | tr '[:upper:]' '[:lower:]')" in
  linux*)
    install_linux_dependencies
    ;;
  darwin*)
    if ! which_cmd brew; then
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
      eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
    fi
    brew update
    brew install curl python openjdk@21 maven go rustup-init >/dev/null || true
    link_macos_jdk
    rustup-init -y
    ;;
  msys*|mingw*|cygwin*)
    echo "Windows detected. Please install curl, Python 3, OpenJDK 21, Maven, Go, and Rust manually." >&2
    exit 1
    ;;
  *)
    echo "Unsupported platform." >&2
    exit 1
    ;;
 esac

echo "Server dependencies installed."
