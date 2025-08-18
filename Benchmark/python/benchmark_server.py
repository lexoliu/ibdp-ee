#!/usr/bin/env python3
"""
Python Benchmark Server for C0 Pure Compute Tests
Note: Expected to show poor performance due to interpreter overhead,
but included for academic rigor to demonstrate with data why Python
is excluded from the main comparison.
"""

import math
import time
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import sys
import multiprocessing

class BenchmarkHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        params = {k: v[0] if v else '' for k, v in parse_qs(parsed_path.query).items()}
        
        if path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
            
        elif path == '/compute/c0a':
            self.handle_c0a(params)
        elif path == '/compute/c0b':
            self.handle_c0b(params)
        elif path == '/compute/c0c':
            self.handle_c0c(params)
        elif path == '/compute/c0d':
            self.handle_c0d(params)
        else:
            self.send_response(404)
            self.end_headers()
    
    def send_json_response(self, data):
        json_str = json.dumps(data)
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json_str.encode())
    
    def handle_c0a(self, params):
        """C0a: Vector dot product/reduction (zero allocation)"""
        size = int(params.get('size', 1000000))
        threads = int(params.get('threads', 1))
        
        # Pre-allocate vectors
        a = [float(i) for i in range(size)]
        b = [float(i * 2) for i in range(size)]
        
        start_time = time.perf_counter()
        
        if threads == 1:
            # Single-threaded dot product
            result = sum(x * y for x, y in zip(a, b))
        else:
            # Multi-threaded version
            chunk_size = size // threads
            
            def compute_chunk(start_idx, end_idx):
                return sum(a[i] * b[i] for i in range(start_idx, end_idx))
            
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = []
                for t in range(threads):
                    start_idx = t * chunk_size
                    end_idx = size if t == threads - 1 else (t + 1) * chunk_size
                    future = executor.submit(compute_chunk, start_idx, end_idx)
                    futures.append(future)
                
                result = sum(future.result() for future in futures)
        
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000
        
        response = {
            'result': result,
            'duration_ms': duration_ms,
            'operations': size
        }
        
        self.send_json_response(response)
    
    def handle_c0b(self, params):
        """C0b: Vectorizable vs branch-intensive computation"""
        size = int(params.get('size', 1000000))
        branchy = params.get('branchy', 'false').lower() == 'true'
        
        data = [i * 0.1 for i in range(size)]
        
        start_time = time.perf_counter()
        
        if branchy:
            # Branch-intensive version
            result = 0.0
            for x in data:
                if x < 0.0:
                    result += x * -1.0
                elif x < 10000.0:
                    result += x * 2.0 + 1.0
                elif x < 50000.0:
                    result += math.sqrt(x)
                else:
                    result += x / 3.0
        else:
            # Vectorizable version
            result = sum(x * 2.0 + 1.0 for x in data)
        
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000
        
        response = {
            'result': result,
            'duration_ms': duration_ms,
            'operations': size
        }
        
        self.send_json_response(response)
    
    def handle_c0c(self, params):
        """C0c: FFT/Convolution (pre-allocated work area)"""
        size = int(params.get('size', 2048))
        
        # Simple discrete convolution as FFT substitute
        signal = [math.sin(i * 0.1) for i in range(size)]
        kernel = [0.25, 0.5, 0.25]  # Simple 3-tap filter
        
        # Pre-allocate output buffer
        output = [0.0] * size
        
        start_time = time.perf_counter()
        
        # Convolution operation (zero additional allocation)
        for i in range(1, size - 1):
            output[i] = (signal[i-1] * kernel[0] + 
                        signal[i] * kernel[1] + 
                        signal[i+1] * kernel[2])
        
        result = sum(output)
        
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000
        
        response = {
            'result': result,
            'duration_ms': duration_ms,
            'operations': size * len(kernel)
        }
        
        self.send_json_response(response)
    
    def handle_c0d(self, params):
        """C0d: Allocation strategy comparison"""
        size = int(params.get('size', 10000))
        use_pool = params.get('use_pool', 'true').lower() == 'true'
        
        start_time = time.perf_counter()
        
        result = 0.0
        
        if use_pool:
            # Pre-allocated strategy
            buffer = [0.0] * 100
            
            for i in range(size):
                # Reuse the same buffer
                for j in range(100):
                    buffer[j] = i + j
                
                result += sum(buffer)
        else:
            # Temporary allocation strategy
            for i in range(size):
                buffer = [i + j for j in range(100)]
                result += sum(buffer)
        
        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000
        
        response = {
            'result': result,
            'duration_ms': duration_ms,
            'operations': size * 100
        }
        
        self.send_json_response(response)
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass

def warmup():
    """Warmup the Python interpreter (though it won't help much)"""
    print("Warming up Python interpreter...")
    
    # Pre-compile some operations
    for _ in range(10):
        a = [float(i) for i in range(10000)]
        b = [float(i * 2) for i in range(10000)]
        sum(x * y for x, y in zip(a, b))
        
        data = [i * 0.1 for i in range(10000)]
        sum(x * 2.0 + 1.0 for x in data)
    
    print("Warmup complete (though Python will still be slow)")

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8083
    
    warmup()
    
    server = HTTPServer(('0.0.0.0', port), BenchmarkHandler)
    print(f"Python benchmark server started on port {port}")
    print("Note: Python performance will be significantly slower than compiled languages")
    print("This server is included for academic completeness to demonstrate the interpreter overhead")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped")
        server.shutdown()

if __name__ == '__main__':
    main()
