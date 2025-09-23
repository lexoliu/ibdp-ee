# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Structure

This repository contains a research project comparing garbage collection performance across Go, Java, and Rust implementations, consisting of:

- **Benchmark/**: Multi-language HTTP service benchmarking harness
- **Paper/**: LaTeX research paper documenting the performance analysis
- **count_words.py**: Word count utility for the paper

## Benchmark Harness

The main component is a comprehensive benchmarking system that compares HTTP service performance across three languages:

### Languages & Frameworks
- **Go**: HTTP service using chi router (go 1.24)
- **Java**: Spring Boot WebFlux service (Java 21, Spring Boot 3.3.3)
- **Rust**: Axum-based async service (Rust 2024 edition)

### Key Components
- `manager.py`: REST API for remote service management
- `benchmark.py`: k6 workload runner and results processor
- `run.py`: Main orchestrator for full benchmark cycles
- `start_service.py`: Local service process management
- `plot_comparison.py`: Results visualization

### k6 Test Scripts
Located in `Benchmark/k6/`:
- `prime.js`: CPU-intensive prime number calculations
- `light.js`: Lightweight request handling
- `kv.js`: Key-value store operations

## Development Commands

### Running Benchmarks

Full benchmark suite:
```bash
cd Benchmark
python run.py --languages java go rust --mode normal
```

Single language test:
```bash
cd Benchmark
python benchmark.py java --mode debug --base-url http://127.0.0.1:8080
```

Manager for remote benchmarking:
```bash
cd Benchmark
python manager.py --bind 0.0.0.0 --port 9000
```

### Service Management

Start individual services:
```bash
cd Benchmark
python start_service.py go --port 8081
python start_service.py java --port 8082
python start_service.py rust --port 8083
```

### Language-Specific Commands

**Go service:**
```bash
cd Benchmark/go
go mod download
go build -o server .
```

**Java service:**
```bash
cd Benchmark/java
mvn clean compile
mvn spring-boot:run
```

**Rust service:**
```bash
cd Benchmark/rust
cargo build --release
cargo run --release
```

### Paper Development

Build paper:
```bash
cd Paper
./build.sh  # Runs update_wordcount.sh then tectonic
```

Update word count:
```bash
cd Paper
./update_wordcount.sh
```

## Important Configuration

### Dependencies
Python requirements are in `Benchmark/requirements.txt`:
- matplotlib==3.7.1
- numpy==1.24.3
- pandas==2.0.3
- resend==2.14.0

### GC Tracing
GC tracing is **enabled by default** for research purposes:
- Go: `GODEBUG=gctrace=1`
- Java: JVM GC logging via `-Xlog:gc`

Use `--disable-gc-trace` to disable when not needed for research.

### Results Structure
Benchmark results are written to `Benchmark/results/<language>/<timestamp>/`:
- `results.json`: Summary metrics and metadata
- `<test>_timeseries.csv`: Per-second RPS and latency percentiles
- `<test>_memory.csv`: RSS memory usage over time
- Raw k6 outputs (if `--keep-raw` is specified)

## Prerequisites

- Python 3.9+
- k6 (for load testing)
- Language toolchains: Go 1.24+, Java 21+, Rust 2024 edition
- tectonic (for paper compilation)

The project includes setup scripts:
- `Benchmark/install_server.sh`: Installs server-side dependencies
- `Benchmark/install_client.sh`: Installs client-side dependencies