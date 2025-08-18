#!/bin/bash

# Comprehensive test script for all benchmark endpoints

SERVER_URL=${1:-"http://localhost:8080"}
OUTPUT_DIR=${2:-"./test_results"}

mkdir -p "$OUTPUT_DIR"

echo "=== Testing Benchmark Server: $SERVER_URL ==="
echo "Results will be saved to: $OUTPUT_DIR"

# Check server health
echo "[*] Testing server health..."
if ! curl -s "$SERVER_URL/health" > /dev/null; then
    echo "❌ Server is not running at $SERVER_URL"
    exit 1
fi
echo "✅ Server is healthy"

# Test C0 Pure Compute endpoints
echo -e "\n=== C0 Pure Compute Tests ==="

echo "[*] C0a: Vector dot product..."
curl -s "$SERVER_URL/compute/c0a?size=100000&threads=1" | jq '.' > "$OUTPUT_DIR/c0a_single.json"
curl -s "$SERVER_URL/compute/c0a?size=100000&threads=4" | jq '.' > "$OUTPUT_DIR/c0a_multi.json"

echo "[*] C0b: Vectorizable vs branchy..."
curl -s "$SERVER_URL/compute/c0b?size=100000&branchy=false" | jq '.' > "$OUTPUT_DIR/c0b_vectorizable.json"
curl -s "$SERVER_URL/compute/c0b?size=100000&branchy=true" | jq '.' > "$OUTPUT_DIR/c0b_branchy.json"

echo "[*] C0c: FFT/Convolution..."
curl -s "$SERVER_URL/compute/c0c?size=2048" | jq '.' > "$OUTPUT_DIR/c0c_fft.json"

echo "[*] C0d: Allocation strategy..."
curl -s "$SERVER_URL/compute/c0d?size=5000&use_pool=true" | jq '.' > "$OUTPUT_DIR/c0d_pooled.json"
curl -s "$SERVER_URL/compute/c0d?size=5000&use_pool=false" | jq '.' > "$OUTPUT_DIR/c0d_temp.json"

# Test Micro endpoints
echo -e "\n=== Micro Tests ==="

echo "[*] A1: Short-lived burst..."
curl -s "$SERVER_URL/compute/a1?ops=5000&size=128" | jq '.' > "$OUTPUT_DIR/a1_burst.json"

echo "[*] A2: Long-lived tidal..."
curl -s "$SERVER_URL/compute/a2?grow=50&chunk_kb=32&max_mb=64" | jq '.' > "$OUTPUT_DIR/a2_tidal.json"

echo "[*] A3: Graph traversal..."
curl -s "$SERVER_URL/compute/a3?steps=500&nodes=500" | jq '.' > "$OUTPUT_DIR/a3_graph.json"

echo "[*] A4: String operations..."
curl -s "$SERVER_URL/compute/a4?rep=200&text_len=500" | jq '.' > "$OUTPUT_DIR/a4_strings.json"

# Test Meso endpoints
echo -e "\n=== Meso Tests ==="

echo "[*] B1: Batch transform..."
curl -s "$SERVER_URL/meso/b1?items=500&transform_type=json" | jq '.' > "$OUTPUT_DIR/b1_json.json"
curl -s "$SERVER_URL/meso/b1?items=500&transform_type=csv" | jq '.' > "$OUTPUT_DIR/b1_csv.json"

echo "[*] B2: Producer-consumer..."
curl -s "$SERVER_URL/meso/b2?produce=2000&chunk=128&consumers=2" | jq '.' > "$OUTPUT_DIR/b2_prodcons.json"

# Test Macro endpoints
echo -e "\n=== Macro Tests ==="

echo "[*] C1: Echo..."
curl -s "$SERVER_URL/echo?msg=Hello&repeat=3" | jq '.' > "$OUTPUT_DIR/c1_echo.json"

echo "[*] C2: Static file..."
curl -s "$SERVER_URL/static/index.html?size=2048" > "$OUTPUT_DIR/c2_static.html"
curl -s "$SERVER_URL/static/data.json?size=1000" | jq '.' > "$OUTPUT_DIR/c2_data.json"

echo "[*] C3: JSON API..."
curl -s "$SERVER_URL/json?items=50&nested=true" | jq '.' > "$OUTPUT_DIR/c3_json_api.json"

echo "[*] C4: Template render..."
curl -s "$SERVER_URL/template?name=TestUser&items=20&theme=default" > "$OUTPUT_DIR/c4_template.html"

echo "[*] C5: Database query..."
curl -s "$SERVER_URL/db/user?id=123&limit=5" | jq '.' > "$OUTPUT_DIR/c5_db.json"

echo -e "\n✅ All tests completed!"
echo "Results saved in: $OUTPUT_DIR"
echo -e "\nQuick performance summary:"
echo "C0a (single-thread): $(jq -r '.duration_ms' $OUTPUT_DIR/c0a_single.json) ms"
echo "C0a (multi-thread): $(jq -r '.duration_ms' $OUTPUT_DIR/c0a_multi.json) ms"
echo "C0b (vectorizable): $(jq -r '.duration_ms' $OUTPUT_DIR/c0b_vectorizable.json) ms"
echo "C0b (branchy): $(jq -r '.duration_ms' $OUTPUT_DIR/c0b_branchy.json) ms"
echo "A1 (burst): $(jq -r '.duration_ms' $OUTPUT_DIR/a1_burst.json) ms"
echo "A4 (strings): $(jq -r '.duration_ms' $OUTPUT_DIR/a4_strings.json) ms"
