use axum::{extract::Query, response::Json};
use serde::{Deserialize, Serialize};
use std::time::Instant;

#[derive(Deserialize)]
pub struct C0aQuery {
    size: Option<usize>,
    threads: Option<usize>,
}

#[derive(Serialize)]
pub struct C0Response {
    result: f64,
    duration_ms: f64,
    operations: usize,
}

/// C0a: Vector dot product/reduction (zero allocation)
pub async fn c0a_vector_dot_product(Query(params): Query<C0aQuery>) -> Json<C0Response> {
    let size = params.size.unwrap_or(1_000_000);
    let threads = params.threads.unwrap_or(1);
    
    // Pre-allocate vectors (not counted as dynamic allocation)
    let a: Vec<f64> = (0..size).map(|i| i as f64).collect();
    let b: Vec<f64> = (0..size).map(|i| (i * 2) as f64).collect();
    
    let start = Instant::now();
    
    let result = if threads == 1 {
        // Single-threaded dot product
        a.iter().zip(b.iter()).map(|(x, y)| x * y).sum::<f64>()
    } else {
        // Multi-threaded using std::thread with Arc for sharing data
        use std::sync::Arc;
        let a_arc = Arc::new(a);
        let b_arc = Arc::new(b);
        let chunk_size = size / threads;
        
        let handles: Vec<_> = (0..threads)
            .map(|i| {
                let start_idx = i * chunk_size;
                let end_idx = if i == threads - 1 { size } else { (i + 1) * chunk_size };
                let a_clone = Arc::clone(&a_arc);
                let b_clone = Arc::clone(&b_arc);
                
                std::thread::spawn(move || {
                    (start_idx..end_idx)
                        .map(|idx| a_clone[idx] * b_clone[idx])
                        .sum::<f64>()
                })
            })
            .collect();
        
        handles.into_iter().map(|h| h.join().unwrap()).sum()
    };
    
    let duration = start.elapsed();
    
    Json(C0Response {
        result,
        duration_ms: duration.as_secs_f64() * 1000.0,
        operations: size,
    })
}

#[derive(Deserialize)]
pub struct C0bQuery {
    size: Option<usize>,
    branchy: Option<bool>,
}

/// C0b: Vectorizable vs branch-intensive computation
pub async fn c0b_vectorizable_vs_branchy(Query(params): Query<C0bQuery>) -> Json<C0Response> {
    let size = params.size.unwrap_or(1_000_000);
    let branchy = params.branchy.unwrap_or(false);
    
    let data: Vec<f64> = (0..size).map(|i| i as f64 * 0.1).collect();
    
    let start = Instant::now();
    
    let result = if branchy {
        // Branch-intensive version
        data.iter()
            .map(|&x| {
                if x < 0.0 {
                    x * -1.0
                } else if x < 10000.0 {
                    x * 2.0 + 1.0
                } else if x < 50000.0 {
                    x.sqrt()
                } else {
                    x / 3.0
                }
            })
            .sum()
    } else {
        // Vectorizable version
        data.iter().map(|&x| x * 2.0 + 1.0).sum()
    };
    
    let duration = start.elapsed();
    
    Json(C0Response {
        result,
        duration_ms: duration.as_secs_f64() * 1000.0,
        operations: size,
    })
}

#[derive(Deserialize)]
pub struct C0cQuery {
    size: Option<usize>,
}

/// C0c: FFT/Convolution (pre-allocated work area)
pub async fn c0c_fft_convolution(Query(params): Query<C0cQuery>) -> Json<C0Response> {
    let size = params.size.unwrap_or(1024);
    
    // Simple discrete convolution as FFT substitute
    let signal: Vec<f64> = (0..size).map(|i| (i as f64 * 0.1).sin()).collect();
    let kernel: Vec<f64> = vec![0.25, 0.5, 0.25]; // Simple 3-tap filter
    
    // Pre-allocate output buffer
    let mut output = vec![0.0; size];
    
    let start = Instant::now();
    
    // Convolution operation (zero additional allocation)
    for i in 1..size - 1 {
        output[i] = signal[i - 1] * kernel[0] + signal[i] * kernel[1] + signal[i + 1] * kernel[2];
    }
    
    let result: f64 = output.iter().sum();
    let duration = start.elapsed();
    
    Json(C0Response {
        result,
        duration_ms: duration.as_secs_f64() * 1000.0,
        operations: size * kernel.len(),
    })
}

#[derive(Deserialize)]
pub struct C0dQuery {
    size: Option<usize>,
    use_pool: Option<bool>,
}

/// C0d: Allocation strategy comparison (pre-allocated vs temporary buffers)
pub async fn c0d_allocation_strategy(Query(params): Query<C0dQuery>) -> Json<C0Response> {
    let size = params.size.unwrap_or(10000);
    let use_pool = params.use_pool.unwrap_or(true);
    
    let start = Instant::now();
    
    let result = if use_pool {
        // Pre-allocated strategy
        let mut buffer = Vec::with_capacity(size);
        let mut sum = 0.0;
        
        for i in 0..size {
            buffer.clear(); // Reuse the same buffer
            for j in 0..100 {
                buffer.push((i + j) as f64);
            }
            sum += buffer.iter().sum::<f64>();
        }
        sum
    } else {
        // Temporary allocation strategy
        let mut sum = 0.0;
        for i in 0..size {
            let buffer: Vec<f64> = (0..100).map(|j| (i + j) as f64).collect();
            sum += buffer.iter().sum::<f64>();
        }
        sum
    };
    
    let duration = start.elapsed();
    
    Json(C0Response {
        result,
        duration_ms: duration.as_secs_f64() * 1000.0,
        operations: size * 100,
    })
}
