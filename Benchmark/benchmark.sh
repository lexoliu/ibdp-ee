#!/bin/bash

set -e

if [ $# -ne 1 ]; then
  echo "Usage: ./benchmark.sh <TaskDirectory>"
  exit 1
fi

TASK_DIR="$1"
ABS_TASK_DIR=$(realpath "$TASK_DIR")
TASK_NAME=$(basename "$ABS_TASK_DIR")
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$ABS_TASK_DIR" ]; then
  echo "❌ Directory not found: $TASK_DIR"
  exit 2
fi

echo ""
echo "=== Benchmarking Task: $TASK_NAME ==="

cd "$ABS_TASK_DIR"

echo "[🔨] Compiling Rust/Go programs..."
[ -f *.rs ]   && rustc *.rs -O -o Rust_"$TASK_NAME"
[ -f *.go ]   && go build -o Go_"$TASK_NAME" *.go

echo "[⚙️] Running hyperfine..."
hyperfine \
  --warmup 3 \
  --runs 10 \
  --export-csv "benchmark_${TASK_NAME}.csv" \
  --export-markdown "benchmark_${TASK_NAME}.md" \
  "./Rust_${TASK_NAME} 1000000" \
  "./Go_${TASK_NAME} 1000000" 
if [ -f "$SCRIPT_DIR/graph.py" ]; then
  "$SCRIPT_DIR/graph.py" "benchmark_${TASK_NAME}.csv"
fi

echo "[✓] Benchmark completed: $TASK_NAME"