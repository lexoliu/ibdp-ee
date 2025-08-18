#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$SCRIPT_DIR"

echo "=== Building Benchmark Servers ==="

# Build Rust server
echo "[*] Building Rust server..."
cd rust
cargo build --release
echo "[✓] Rust server built: target/release/server"
cd ..

# Build Go server
echo "[*] Building Go server..."
cd go
go build -o server .
echo "[✓] Go server built: server"
cd ..

# Build Java server
echo "[*] Building Java server..."
cd java
javac JavaBenchmarkServer.java
echo "[✓] Java server compiled"
cd ..

# Python server is interpreted, no build needed
echo "[✓] Python server ready (interpreted)"

echo "=== All servers built successfully ==="
echo ""
echo "Usage:"
echo "  ./run.sh rust     # Start Rust server on port 8080"
echo "  ./run.sh go       # Start Go server on port 8081"
echo "  ./run.sh java     # Start Java server on port 8082"
echo "  ./run.sh python   # Start Python server on port 8083"
echo ""
echo "Note: Java and Python are expected to show poor C0 performance"
echo "      and will likely be excluded from main analysis based on data"
