#!/bin/bash

# Build the paper using Typst
# Word count is automatically calculated by the wordometer package

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --root .. allows access to ../Benchmark/ for plots
typst compile --root .. ./main.typ
