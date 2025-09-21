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

install_k6_linux() {
  if which_cmd k6; then
    echo "✔ k6 already installed"
    return
  fi
  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing k6 via apt repository"
    sudo apt-get update
    sudo apt-get install -y gnupg software-properties-common ca-certificates
    curl -fsSL https://dl.k6.io/key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/k6-archive-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list >/dev/null
    sudo apt-get update
    sudo apt-get install -y k6
  elif command -v dnf >/dev/null 2>&1; then
    echo "Installing k6 via dnf repository"
    sudo dnf install -y https://dl.k6.io/rpm/repo.rpm
    sudo dnf install -y k6
  elif command -v yum >/dev/null 2>&1; then
    echo "Installing k6 via yum repository"
    sudo yum install -y https://dl.k6.io/rpm/repo.rpm
    sudo yum install -y k6
  else
    echo "Unsupported Linux distribution. Please install k6 manually: https://grafana.com/docs/k6/latest/get-started/installation/"
    exit 1
  fi
}

install_with_pkgman() {
  local packages=("$@")
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y "${packages[@]}"
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y "${packages[@]}"
  elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y "${packages[@]}"
  else
    return 1
  fi
}

ensure_linux_cmd() {
  local cmd="$1"
  shift
  local packages=("$@")
  if which_cmd "$cmd"; then
    echo "✔ $cmd already installed"
    return
  fi
  echo "Installing packages for $cmd: ${packages[*]}"
  if ! install_with_pkgman "${packages[@]}"; then
    echo "Unsupported Linux package manager. Install $cmd manually." >&2
    exit 1
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
    ensure_linux_cmd curl curl
    ensure_linux_cmd python3 python3 python3-venv python3-pip
    install_k6_linux
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
