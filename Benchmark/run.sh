#!/bin/bash

set -e

if [ $# -ne 1 ]; then
  echo "Usage: ./run.sh [rust|go|java]"
  exit 1
fi

LANGUAGE="$1"
TASK_DIR=$(pwd)
TASK_NAME=$(basename "$TASK_DIR")
CAP_TASK=$(echo "$TASK_NAME" | sed -E 's/(^|_)([a-z])/\U\2/g')

case "$LANGUAGE" in
  rust)
    BIN="./Rust_${CAP_TASK} 100000"
    if [[ -x "$BIN" ]]; then
      echo "[*] Running Rust: $BIN"
      "$BIN"
    else
      echo "❌ Rust executable not found: $BIN"
      exit 2
    fi
    ;;
  go)
    BIN="./Go_${CAP_TASK} 100000"
    if [[ -x "$BIN" ]]; then
      echo "[*] Running Go: $BIN"
      "$BIN"
    else
      echo "❌ Go executable not found: $BIN"
      exit 2
    fi
    ;;
  java)
    CLASS_NAME="${CAP_TASK}"
    if [[ -f "$CLASS_NAME.class" ]]; then
      echo "[*] Running Java: $CLASS_NAME"
      java "$CLASS_NAME 100000"
    else
      echo "❌ Java class not found: $CLASS_NAME.class"
      exit 2
    fi
    ;;
  *)
    echo "❌ Unsupported language: $LANGUAGE"
    echo "   Use: rust | go | java"
    exit 3
    ;;
esac