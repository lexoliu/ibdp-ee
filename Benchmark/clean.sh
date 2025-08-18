#!/bin/bash

echo "[*] Cleaning up Rust, Go, and Java build artifacts..."

find . -type f \( -name 'Rust_*' -o -name 'Go_*' -o -name '*.class' \) | while read file; do
  if [[ -x "$file" || "$file" == *.class ]]; then
    echo "  [Removed] $file"
    rm -f "$file"
  fi
done

cd "./WebServer/rust"
cargo clean

echo "[✓] Cleanup complete."