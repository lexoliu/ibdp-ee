#!/bin/bash

set -e

echo "=== Benchmark Setup Script ==="

OS="$(uname -s)"

echo "[*] Detecting OS: $OS"

install_rust() {
  if ! command -v rustc >/dev/null 2>&1; then
    echo "[*] Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    export PATH="$HOME/.cargo/bin:$PATH"
  else
    echo "[✓] Rust already installed."
  fi
}

install_go() {
  if ! command -v go >/dev/null 2>&1; then
    echo "[*] Installing Go..."

    if [[ "$OS" == "Darwin" ]]; then
      brew install go
    elif [[ "$OS" == "Linux" ]]; then
      sudo apt update
      sudo apt install -y golang
    fi
  else
    echo "[✓] Go already installed."
  fi
}

install_java() {
  if ! command -v javac >/dev/null 2>&1; then
    echo "[*] Installing OpenJDK..."

    if [[ "$OS" == "Darwin" ]]; then
      brew install openjdk
      sudo ln -sfn $(brew --prefix openjdk)/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk.jdk
      echo 'export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"' >> ~/.zprofile
    elif [[ "$OS" == "Linux" ]]; then
      sudo apt update
      sudo apt install -y openjdk-17-jdk
    fi
  else
    echo "[✓] Java already installed."
  fi
}

install_hyperfine() {
  if ! command -v hyperfine >/dev/null 2>&1; then
    echo "[*] Installing hyperfine..."

    if [[ "$OS" == "Darwin" ]]; then
      brew install hyperfine
    elif [[ "$OS" == "Linux" ]]; then
      sudo apt update
      sudo apt install -y hyperfine
    fi
  else
    echo "[✓] hyperfine already installed."
  fi
}

# Start installation
install_rust
install_go
install_java
install_hyperfine

echo ""
echo "[✓] All required tools installed successfully."
echo "➡️  Please restart your terminal or run: source ~/.bashrc (or ~/.zshrc)"