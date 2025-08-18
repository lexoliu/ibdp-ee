#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$SCRIPT_DIR"

LANG=$1
PORT=${2:-"auto"}

if [ -z "$LANG" ]; then
    echo "Usage: $0 <language> [port]"
    echo "  language: rust, go, java, python"
    echo "  port: auto assigns default ports (8080, 8081, 8082, 8083)"
    echo "        or specify custom port"
    exit 1
fi

# Auto-assign ports if not specified
if [ "$PORT" = "auto" ]; then
    case $LANG in
        rust) PORT=8080 ;;
        go) PORT=8081 ;;
        java) PORT=8082 ;;
        python) PORT=8083 ;;
    esac
fi

case $LANG in
    rust)
        echo "[*] Starting Rust server on port $PORT..."
        cd rust
        RUST_LOG=info ./target/release/server
        ;;
    go)
        echo "[*] Starting Go server on port $PORT..."
        cd go
        PORT=$PORT ./server
        ;;
    java)
        echo "[*] Starting Java server on port $PORT..."
        cd java
        echo "    Note: Java expected to show poor C0 performance due to JIT compilation overhead"
        java -Xms2g -Xmx2g JavaBenchmarkServer $PORT
        ;;
    python)
        echo "[*] Starting Python server on port $PORT..."
        cd python
        echo "    Note: Python expected to show very poor performance due to interpreter overhead"
        python3 benchmark_server.py $PORT
        ;;
    *)
        echo "Unknown language: $LANG"
        echo "Supported: rust, go, java, python"
        exit 1
        ;;
esac
