package main

import (
	"math"
	"net/http"
	"runtime"
	"sync"
	"time"
)

type C0Response struct {
	Result      float64 `json:"result"`
	DurationMs  float64 `json:"duration_ms"`
	Operations  int     `json:"operations"`
}

// C0a: Vector dot product/reduction (zero allocation)
func c0aVectorDotProduct(state *AppState, w http.ResponseWriter, r *http.Request) {
	size := getQueryParamInt(r, "size", 1000000)
	threads := getQueryParamInt(r, "threads", 1)
	
	// Pre-allocate vectors (not counted as dynamic allocation)
	a := make([]float64, size)
	b := make([]float64, size)
	
	for i := 0; i < size; i++ {
		a[i] = float64(i)
		b[i] = float64(i * 2)
	}
	
	start := time.Now()
	
	var result float64
	
	if threads == 1 {
		// Single-threaded dot product
		for i := 0; i < size; i++ {
			result += a[i] * b[i]
		}
	} else {
		// Multi-threaded
		numCPU := runtime.NumCPU()
		if threads > numCPU {
			threads = numCPU
		}
		
		chunkSize := size / threads
		var wg sync.WaitGroup
		results := make([]float64, threads)
		
		for t := 0; t < threads; t++ {
			wg.Add(1)
			go func(threadID int) {
				defer wg.Done()
				start := threadID * chunkSize
				end := start + chunkSize
				if threadID == threads-1 {
					end = size
				}
				
				var sum float64
				for i := start; i < end; i++ {
					sum += a[i] * b[i]
				}
				results[threadID] = sum
			}(t)
		}
		
		wg.Wait()
		
		for _, partial := range results {
			result += partial
		}
	}
	
	duration := time.Since(start)
	
	response := C0Response{
		Result:     result,
		DurationMs: float64(duration.Nanoseconds()) / 1e6,
		Operations: size,
	}
	
	writeJSONResponse(w, response)
}

// C0b: Vectorizable vs branch-intensive computation
func c0bVectorizableVsBranchy(state *AppState, w http.ResponseWriter, r *http.Request) {
	size := getQueryParamInt(r, "size", 1000000)
	branchy := getQueryParamBool(r, "branchy", false)
	
	data := make([]float64, size)
	for i := 0; i < size; i++ {
		data[i] = float64(i) * 0.1
	}
	
	start := time.Now()
	
	var result float64
	
	if branchy {
		// Branch-intensive version
		for _, x := range data {
			if x < 0.0 {
				result += x * -1.0
			} else if x < 10000.0 {
				result += x*2.0 + 1.0
			} else if x < 50000.0 {
				result += math.Sqrt(x)
			} else {
				result += x / 3.0
			}
		}
	} else {
		// Vectorizable version
		for _, x := range data {
			result += x*2.0 + 1.0
		}
	}
	
	duration := time.Since(start)
	
	response := C0Response{
		Result:     result,
		DurationMs: float64(duration.Nanoseconds()) / 1e6,
		Operations: size,
	}
	
	writeJSONResponse(w, response)
}

// C0c: FFT/Convolution (pre-allocated work area)
func c0cFFTConvolution(state *AppState, w http.ResponseWriter, r *http.Request) {
	size := getQueryParamInt(r, "size", 1024)
	
	// Simple discrete convolution as FFT substitute
	signal := make([]float64, size)
	kernel := []float64{0.25, 0.5, 0.25} // Simple 3-tap filter
	
	for i := 0; i < size; i++ {
		signal[i] = math.Sin(float64(i) * 0.1)
	}
	
	// Pre-allocate output buffer
	output := make([]float64, size)
	
	start := time.Now()
	
	// Convolution operation (zero additional allocation)
	for i := 1; i < size-1; i++ {
		output[i] = signal[i-1]*kernel[0] + signal[i]*kernel[1] + signal[i+1]*kernel[2]
	}
	
	var result float64
	for _, val := range output {
		result += val
	}
	
	duration := time.Since(start)
	
	response := C0Response{
		Result:     result,
		DurationMs: float64(duration.Nanoseconds()) / 1e6,
		Operations: size * len(kernel),
	}
	
	writeJSONResponse(w, response)
}

// C0d: Allocation strategy comparison (pre-allocated vs temporary buffers)
func c0dAllocationStrategy(state *AppState, w http.ResponseWriter, r *http.Request) {
	size := getQueryParamInt(r, "size", 10000)
	usePool := getQueryParamBool(r, "use_pool", true)
	
	start := time.Now()
	
	var result float64
	
	if usePool {
		// Pre-allocated strategy
		buffer := make([]float64, 100)
		
		for i := 0; i < size; i++ {
			// Clear and reuse the same buffer
			for j := range buffer {
				buffer[j] = 0
			}
			
			for j := 0; j < 100; j++ {
				buffer[j] = float64(i + j)
			}
			
			for _, val := range buffer {
				result += val
			}
		}
	} else {
		// Temporary allocation strategy
		for i := 0; i < size; i++ {
			buffer := make([]float64, 100)
			for j := 0; j < 100; j++ {
				buffer[j] = float64(i + j)
			}
			
			for _, val := range buffer {
				result += val
			}
		}
	}
	
	duration := time.Since(start)
	
	response := C0Response{
		Result:     result,
		DurationMs: float64(duration.Nanoseconds()) / 1e6,
		Operations: size * 100,
	}
	
	writeJSONResponse(w, response)
}
