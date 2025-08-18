# Benchmark-v2: GC vs Non-GC Performance Evaluation

This is a comprehensive benchmark suite designed to evaluate the performance impact of garbage collection in real-world applications. The project implements identical benchmark tasks across multiple languages to isolate the effects of memory management strategies.

## Project Structure

```
Benchmark-v2/
├── rust/           # Rust implementation (non-GC, manual memory management)
│   ├── src/
│   │   ├── main.rs                 # Main server and routing
│   │   ├── c0_pure_compute.rs      # C0: Pure compute benchmarks
│   │   ├── micro_tests.rs          # Micro: Memory behavior tests
│   │   ├── meso_tests.rs           # Meso: Medium-scale tests
│   │   └── macro_tests.rs          # Macro: End-to-end web tests
│   └── Cargo.toml
├── go/             # Go implementation (GC)
│   ├── main.go
│   ├── c0_tests.go
│   ├── micro_tests.go
│   ├── meso_tests.go
│   ├── macro_tests.go
│   └── go.mod
├── java/           # Java implementation (GC) [TODO]
├── build.sh        # Build all servers
├── run.sh          # Start specific language server
└── test_all.sh     # Comprehensive endpoint testing
```

## Benchmark Categories

### C0 Pure Compute (Negative Control)
Tests with minimal/zero heap allocation to establish performance baseline:
- **C0a**: Vector dot product (single/multi-threaded)
- **C0b**: Vectorizable vs branch-intensive computation
- **C0c**: FFT/Convolution with pre-allocated buffers
- **C0d**: Allocation strategy comparison (pooled vs temporary)

### Micro Tests (Memory Behavior Isolation)
Tests focusing on specific memory allocation patterns:
- **A1**: Short-lived small object burst (16-128B)
- **A2**: Long-lived set with tidal growth
- **A3**: Random graph traversal (pointer chasing)
- **A4**: String operations (temporary object flood)

### Meso Tests (Medium Scale)
Medium-complexity scenarios with realistic allocation patterns:
- **B1**: Batch data transformation (CSV/JSON processing)
- **B2**: Multi-producer multi-consumer queue

### Macro Tests (End-to-End Web)
Real-world web application scenarios:
- **C1**: Echo endpoint (minimal framework overhead)
- **C2**: Static file serving
- **C3**: JSON API with complex serialization
- **C4**: Server-side template rendering
- **C5**: Database query simulation

## Quick Start

1. **Build all servers:**
   ```bash
   ./build.sh
   ```

2. **Start a server:**
   ```bash
   # Start Rust server on port 8080
   ./run.sh rust
   
   # Start Go server on port 8081
   ./run.sh go 8081
   ```

3. **Test all endpoints:**
   ```bash
   # Test running server
   ./test_all.sh http://localhost:8080
   ```

## API Endpoints

All servers expose identical REST APIs:

### C0 Pure Compute
- `GET /compute/c0a?size=1000000&threads=1` - Vector dot product
- `GET /compute/c0b?size=1000000&branchy=false` - Vectorizable computation
- `GET /compute/c0c?size=2048` - FFT/Convolution
- `GET /compute/c0d?size=10000&use_pool=true` - Allocation strategy

### Micro Tests
- `GET /compute/a1?ops=10000&size=64` - Short-lived burst
- `GET /compute/a2?grow=100&chunk_kb=64&max_mb=256` - Tidal growth
- `GET /compute/a3?steps=1000&nodes=1000` - Graph traversal
- `GET /compute/a4?rep=1000&text_len=1000` - String operations

### Meso Tests
- `GET /meso/b1?items=1000&transform_type=json` - Batch transform
- `GET /meso/b2?produce=10000&chunk=256&consumers=2` - Producer-consumer

### Macro Tests
- `GET /echo?msg=hello&repeat=3` - Echo
- `GET /static/index.html?size=2048` - Static file
- `GET /json?items=100&nested=true` - JSON API
- `GET /template?name=User&items=50&theme=default` - Template
- `GET /db/user?id=123&limit=10` - Database query

## Experimental Variables

- **T (Treatment)**: Memory management (Rust vs Go vs Java)
- **L (Load)**: Intensity (Low/Medium/High saturation)
- **W (Workload)**: Task type (C0/Micro/Meso/Macro)
- **C (Concurrency)**: Single-thread vs High concurrency
- **S (Strategy)**: Pre-allocated vs Temporary allocation

## Response Format

All endpoints return timing and performance metrics:

```json
{
  "duration_ms": 1.234,
  "operations": 10000,
  "result": "...",
  "allocations": 1000
}
```

## Performance Testing

Use tools like `wrk`, `hey`, or `k6` for load testing:

```bash
# Example: Load test C0a endpoint
wrk -t4 -c100 -d30s "http://localhost:8080/compute/c0a?size=100000"

# Example: Load test JSON API
wrk -t4 -c100 -d30s "http://localhost:8080/json?items=50"
```

## Research Methodology

This benchmark follows a rigorous experimental design:

1. **Causal Framework**: Isolate GC effects from other confounders
2. **Crossover Design**: Each configuration tested with both languages
3. **Negative Control**: C0 tests verify baseline equivalence
4. **Statistical Analysis**: Mann-Whitney U, effect sizes, equivalence testing
5. **Multiple Comparison Correction**: Benjamini-Hochberg FDR control

## Citation

If you use this benchmark in research, please cite:

```
Performance Impact of Garbage Collection in Real-World Applications
Lexo Liu, 2025
International Baccalaureate Diploma Programme Extended Essay
```
