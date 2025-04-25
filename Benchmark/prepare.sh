#!/bin/bash

set -e

echo "[*] Preparing all Rust, Go, and Java programs in: $(pwd)"

find . -type f \( -name '*.rs' -o -name '*.go' -o -name '*.java' \) | while read file; do
  abs_path="$(realpath "$file")"
  dir_path="$(dirname "$abs_path")"
  base="$(basename "$file")"
  ext="${base##*.}"
  task="$(basename "$dir_path")"

  cd "$dir_path"

  if [[ "$ext" == "rs" ]]; then
    out="Rust_${task}"
    echo "  [Rust] Compiling $base → $out"
    rustc -C opt-level=3 "$base" -o "$out"
    chmod +x "$out"
  elif [[ "$ext" == "go" ]]; then
    out="Go_${task}"
    echo "  [Go] Compiling $base → $out"
    go build -o "$out" "$base"
    chmod +x "$out"
  elif [[ "$ext" == "java" ]]; then
    class_name="${base%.java}"
    echo "  [Java] Compiling $base → $class_name.class"
    javac "$base"
  fi

  cd - > /dev/null
done

echo "[✓] All programs prepared."