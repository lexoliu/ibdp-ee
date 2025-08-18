#!/bin/bash

# C0 Baseline Equivalence Test Script
# This script tests all languages on C0 pure compute tasks to establish baseline performance
# and demonstrate with data why certain languages should be excluded from main analysis

echo "=== C0 Pure Compute Baseline Test ==="
echo "Testing all languages on zero-allocation compute tasks"
echo "Expected results:"
echo "  - Rust & Go: Similar performance (baseline equivalence)"
echo "  - Java: Slower due to JIT compilation overhead"
echo "  - Python: Much slower due to interpreter overhead"
echo ""

# Configuration
RUST_PORT=8080
GO_PORT=8081
JAVA_PORT=8082
PYTHON_PORT=8083

TEST_PARAMS="size=100000"
ITERATIONS=5

echo "Test parameters: $TEST_PARAMS"
echo "Iterations per test: $ITERATIONS"
echo ""

# Function to test a specific endpoint
test_endpoint() {
    local name=$1
    local url=$2
    local iterations=$3
    
    echo "Testing $name..."
    
    local total_time=0
    local times=()
    
    for i in $(seq 1 $iterations); do
        if response=$(curl -s "$url" 2>/dev/null); then
            if duration=$(echo "$response" | grep -o '"duration_ms":[0-9.]*' | cut -d: -f2); then
                times+=($duration)
                total_time=$(echo "$total_time + $duration" | bc -l)
                echo "  Run $i: ${duration}ms"
            else
                echo "  Run $i: Failed to parse response"
                return 1
            fi
        else
            echo "  Run $i: Request failed"
            return 1
        fi
    done
    
    local avg_time=$(echo "scale=3; $total_time / $iterations" | bc -l)
    echo "  Average: ${avg_time}ms"
    echo ""
}

# Function to check if server is running
check_server() {
    local name=$1
    local port=$2
    
    if curl -s "http://localhost:$port/health" > /dev/null 2>&1; then
        echo "✅ $name server (port $port) is running"
        return 0
    else
        echo "❌ $name server (port $port) is not running"
        return 1
    fi
}

# Check all servers
echo "=== Server Status Check ==="
rust_ok=false
go_ok=false
java_ok=false
python_ok=false

check_server "Rust" $RUST_PORT && rust_ok=true
check_server "Go" $GO_PORT && go_ok=true
check_server "Java" $JAVA_PORT && java_ok=true
check_server "Python" $PYTHON_PORT && python_ok=true

echo ""

if [ "$rust_ok" = false ] && [ "$go_ok" = false ] && [ "$java_ok" = false ] && [ "$python_ok" = false ]; then
    echo "❌ No servers are running. Please start servers first:"
    echo "   Terminal 1: ./run.sh rust"
    echo "   Terminal 2: ./run.sh go"
    echo "   Terminal 3: ./run.sh java"
    echo "   Terminal 4: ./run.sh python"
    exit 1
fi

# Run C0 tests on available servers
echo "=== C0a: Vector Dot Product Test ==="

if [ "$rust_ok" = true ]; then
    test_endpoint "Rust C0a" "http://localhost:$RUST_PORT/compute/c0a?$TEST_PARAMS" $ITERATIONS
fi

if [ "$go_ok" = true ]; then
    test_endpoint "Go C0a" "http://localhost:$GO_PORT/compute/c0a?$TEST_PARAMS" $ITERATIONS
fi

if [ "$java_ok" = true ]; then
    test_endpoint "Java C0a" "http://localhost:$JAVA_PORT/compute/c0a?$TEST_PARAMS" $ITERATIONS
fi

if [ "$python_ok" = true ]; then
    test_endpoint "Python C0a" "http://localhost:$PYTHON_PORT/compute/c0a?$TEST_PARAMS" $ITERATIONS
fi

echo "=== C0b: Vectorizable Computation Test ==="

if [ "$rust_ok" = true ]; then
    test_endpoint "Rust C0b" "http://localhost:$RUST_PORT/compute/c0b?$TEST_PARAMS&branchy=false" $ITERATIONS
fi

if [ "$go_ok" = true ]; then
    test_endpoint "Go C0b" "http://localhost:$GO_PORT/compute/c0b?$TEST_PARAMS&branchy=false" $ITERATIONS
fi

if [ "$java_ok" = true ]; then
    test_endpoint "Java C0b" "http://localhost:$JAVA_PORT/compute/c0b?$TEST_PARAMS&branchy=false" $ITERATIONS
fi

if [ "$python_ok" = true ]; then
    test_endpoint "Python C0b" "http://localhost:$PYTHON_PORT/compute/c0b?$TEST_PARAMS&branchy=false" $ITERATIONS
fi

echo "=== C0c: FFT/Convolution Test ==="

if [ "$rust_ok" = true ]; then
    test_endpoint "Rust C0c" "http://localhost:$RUST_PORT/compute/c0c?size=2048" $ITERATIONS
fi

if [ "$go_ok" = true ]; then
    test_endpoint "Go C0c" "http://localhost:$GO_PORT/compute/c0c?size=2048" $ITERATIONS
fi

if [ "$java_ok" = true ]; then
    test_endpoint "Java C0c" "http://localhost:$JAVA_PORT/compute/c0c?size=2048" $ITERATIONS
fi

if [ "$python_ok" = true ]; then
    test_endpoint "Python C0c" "http://localhost:$PYTHON_PORT/compute/c0c?size=2048" $ITERATIONS
fi

echo "=== Summary & Analysis ==="
echo "C0 tests completed. Expected findings:"
echo ""
echo "1. BASELINE EQUIVALENCE (Rust vs Go):"
echo "   - Should show similar performance (within ±10% equivalence boundary)"
echo "   - Validates that GC overhead is negligible in zero-allocation scenarios"
echo "   - Establishes that Rust and Go are suitable for main comparison"
echo ""
echo "2. CONFOUNDING FACTORS (Java):"
echo "   - Likely shows slower performance due to JIT compilation overhead"
echo "   - Even after warmup, may not reach native performance in short tests"
echo "   - Demonstrates why JIT vs AOT is a confounding variable"
echo ""
echo "3. EXTREME OVERHEAD (Python):"
echo "   - Expected to be 10-100x slower than compiled languages"
echo "   - Clearly demonstrates interpreter overhead as dominant factor"
echo "   - Justifies exclusion from main GC vs non-GC comparison"
echo ""
echo "These results provide empirical justification for focusing the main"
echo "experimental comparison on Rust (non-GC) vs Go (GC) only."
