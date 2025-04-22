#!/bin/bash

set -e

echo "Updating package manager..."
if command -v apt &> /dev/null; then
    sudo apt update
elif command -v dnf &> /dev/null; then
    sudo dnf check-update
elif command -v yum &> /dev/null; then
    sudo yum check-update
elif command -v pacman &> /dev/null; then
    sudo pacman -Sy
elif command -v brew &> /dev/null; then
    brew update
fi

echo "Installing Python dependencies..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install py-spy matplotlib

deactivate
echo "Python dependencies installed in virtual environment. Use 'source .venv/bin/activate' before running scripts."

echo "Installing Flamegraph..."
if command -v brew &> /dev/null; then
    brew install flamegraph
elif command -v apt &> /dev/null; then
    sudo apt install -y flamegraph
elif command -v pacman &> /dev/null; then
    sudo pacman -S --noconfirm flamegraph
else
    echo "Cannot automatically install Flamegraph, please install manually: https://github.com/brendangregg/FlameGraph"
fi

if ! command -v go &> /dev/null; then
    echo "Installing Go..."
    if command -v apt &> /dev/null; then
        sudo apt install -y golang
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y golang
    elif command -v yum &> /dev/null; then
        sudo yum install -y golang
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm go
    elif command -v brew &> /dev/null; then
        brew install go
    else
        echo "Cannot automatically install Go, please install manually: https://golang.org/doc/install"
    fi
fi

if ! command -v javac &> /dev/null; then
    echo "Installing Java Development Kit..."
    if command -v apt &> /dev/null; then
        sudo apt install -y default-jdk
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y java-latest-openjdk-devel
    elif command -v yum &> /dev/null; then
        sudo yum install -y java-devel
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm jdk-openjdk
    elif command -v brew &> /dev/null; then
        brew install openjdk
    else
        echo "Cannot automatically install Java JDK, please install manually: https://www.oracle.com/java/technologies/javase-downloads.html"
    fi
fi

if ! command -v rustc &> /dev/null; then
    echo "Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source $HOME/.cargo/env
fi

echo "Installation complete!"
echo "Now you can run your performance test script using Flamegraph."
