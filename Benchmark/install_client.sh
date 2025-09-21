#!/usr/bin/env bash
set -euo pipefail

which_cmd() {
  command -v "$1" >/dev/null 2>&1
}

require() {
  local cmd="$1"
  local package="$2"
  if which_cmd "$cmd"; then
    echo "✔ $cmd already installed"
  else
    echo "Installing $package for $cmd"
    eval "$3"
  fi
}

detect_platform() {
  local uname
  uname=$(uname -s | tr '[:upper:]' '[:lower:]')
  case "$uname" in
    linux*) echo linux ;;
    darwin*) echo macos ;;
    msys*|mingw*|cygwin*) echo windows ;;
    *) echo unknown ;;
  esac
}

PLATFORM=$(detect_platform)
echo "Detected platform: $PLATFORM"

case "$PLATFORM" in
  linux)
    require curl curl 'sudo apt-get update && sudo apt-get install -y curl'
    require python3 python3 'sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip'
    require k6 k6 'curl -s https://raw.githubusercontent.com/grafana/k6/master/install.sh | bash'
    ;;
  macos)
    require brew brew '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    require python3 python3 'brew install python'
    require k6 k6 'brew install k6'
    ;;
  windows)
    echo "Please install dependencies manually on Windows: curl, Python 3, k6."
    exit 1
    ;;
  *)
    echo "Unsupported platform: $PLATFORM"
    exit 1
    ;;
 esac

echo "Client dependencies installed."
