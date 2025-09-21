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
    require java java 'sudo apt-get update && sudo apt-get install -y default-jdk'
    require mvn mvn 'sudo apt-get update && sudo apt-get install -y maven'
    require go go 'sudo apt-get update && sudo apt-get install -y golang-go'
    require cargo cargo 'sudo apt-get update && sudo apt-get install -y cargo'
    ;;
  macos)
    require brew brew '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    require java java 'brew install openjdk'
    require mvn mvn 'brew install maven'
    require go go 'brew install go'
    require cargo cargo 'brew install rustup-init && rustup-init -y'
    ;;
  windows)
    echo "Please install dependencies manually on Windows: curl, Java (JDK), Maven, Go, Rust (cargo)."
    exit 1
    ;;
  *)
    echo "Unsupported platform: $PLATFORM"
    exit 1
    ;;
 esac

echo "Server dependencies installed."
