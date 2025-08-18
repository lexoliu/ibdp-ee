use axum::{extract::Query, response::Json};
use serde::{Deserialize, Serialize};
use std::time::Instant;

#[derive(Serialize)]
pub struct MicroResponse {
    operations: usize,
    duration_ms: f64,
    allocations: usize,
    result: Option<String>,
}

#[derive(Deserialize)]
pub struct A1Query {
    ops: Option<usize>,
    size: Option<usize>,
}

/// A1: Short-lived small object burst (16-128B, escape control)
pub async fn a1_short_lived_burst(Query(params): Query<A1Query>) -> Json<MicroResponse> {
    let ops = params.ops.unwrap_or(10000);
    let size = params.size.unwrap_or(64);
    
    let start = Instant::now();
    
    let mut total_sum = 0u64;
    let mut allocations = 0;
    
    for _ in 0..ops {
        // Create short-lived small objects
        let data: Vec<u8> = (0..size).map(|i| (i % 256) as u8).collect();
        allocations += 1;
        
        // Do some computation to prevent optimization
        total_sum += data.iter().map(|&b| b as u64).sum::<u64>();
        
        // Object goes out of scope here (short-lived)
    }
    
    let duration = start.elapsed();
    
    Json(MicroResponse {
        operations: ops,
        duration_ms: duration.as_secs_f64() * 1000.0,
        allocations,
        result: Some(format!("sum_{}", total_sum)),
    })
}

#[derive(Deserialize)]
pub struct A2Query {
    grow: Option<usize>,
    chunk_kb: Option<usize>,
    max_mb: Option<usize>,
}

/// A2: Long-lived set + tidal growth (live set slowly rises)
pub async fn a2_long_lived_tidal(Query(params): Query<A2Query>) -> Json<MicroResponse> {
    let grow_steps = params.grow.unwrap_or(100);
    let chunk_kb = params.chunk_kb.unwrap_or(64);
    let max_mb = params.max_mb.unwrap_or(256);
    
    let chunk_size = chunk_kb * 1024;
    let max_chunks = (max_mb * 1024 * 1024) / chunk_size;
    
    let start = Instant::now();
    
    let mut live_set: Vec<Vec<u8>> = Vec::new();
    let mut allocations = 0;
    
    for step in 0..grow_steps {
        // Tidal growth: add chunks but occasionally remove old ones
        if live_set.len() < max_chunks {
            let chunk: Vec<u8> = (0..chunk_size).map(|i| ((step + i) % 256) as u8).collect();
            live_set.push(chunk);
            allocations += 1;
        }
        
        // Occasionally remove old data (tidal effect)
        if step % 20 == 0 && !live_set.is_empty() {
            live_set.remove(0);
        }
        
        // Access random parts to keep data "live"
        if !live_set.is_empty() {
            let idx = step % live_set.len();
            let _ = live_set[idx].iter().sum::<u8>();
        }
    }
    
    let duration = start.elapsed();
    
    Json(MicroResponse {
        operations: grow_steps,
        duration_ms: duration.as_secs_f64() * 1000.0,
        allocations,
        result: Some(format!("live_chunks_{}", live_set.len())),
    })
}

// Simple graph structure for A3
#[derive(Clone)]
struct GraphNode {
    value: i32,
    neighbors: Vec<usize>,
}

#[derive(Deserialize)]
pub struct A3Query {
    steps: Option<usize>,
    nodes: Option<usize>,
}

/// A3: Random graph traversal (pointer chasing + write barrier cost)
pub async fn a3_graph_traversal(Query(params): Query<A3Query>) -> Json<MicroResponse> {
    let steps = params.steps.unwrap_or(1000);
    let node_count = params.nodes.unwrap_or(1000);
    
    let start = Instant::now();
    
    // Build a random graph
    let mut graph: Vec<GraphNode> = Vec::with_capacity(node_count);
    let mut rng = rand::thread_rng();
    use rand::Rng;
    
    for i in 0..node_count {
        let neighbors: Vec<usize> = (0..5)
            .map(|_| rng.gen_range(0..node_count))
            .collect();
        
        graph.push(GraphNode {
            value: i as i32,
            neighbors,
        });
    }
    
    // Random graph traversal
    let mut current = 0;
    let mut visited_sum = 0i64;
    let allocations = graph.len();
    
    for _ in 0..steps {
        visited_sum += graph[current].value as i64;
        
        // Update node value (triggers write barrier in GC languages)
        graph[current].value += 1;
        
        // Move to random neighbor
        if !graph[current].neighbors.is_empty() {
            let next_idx = rng.gen_range(0..graph[current].neighbors.len());
            current = graph[current].neighbors[next_idx];
        }
    }
    
    let duration = start.elapsed();
    
    Json(MicroResponse {
        operations: steps,
        duration_ms: duration.as_secs_f64() * 1000.0,
        allocations,
        result: Some(format!("visited_sum_{}", visited_sum)),
    })
}

#[derive(Deserialize)]
pub struct A4Query {
    rep: Option<usize>,
    text_len: Option<usize>,
}

/// A4: String parsing/concatenation (temporary object flood)
pub async fn a4_string_operations(Query(params): Query<A4Query>) -> Json<MicroResponse> {
    let repetitions = params.rep.unwrap_or(1000);
    let text_len = params.text_len.unwrap_or(1000);
    
    let base_text = "a".repeat(text_len);
    
    let start = Instant::now();
    
    let mut result_strings = Vec::new();
    let mut allocations = 0;
    
    for i in 0..repetitions {
        // String operations that create temporary objects
        let processed = base_text
            .chars()
            .enumerate()
            .map(|(idx, c)| {
                if idx % 2 == 0 {
                    c.to_uppercase().collect::<String>()
                } else {
                    c.to_lowercase().collect::<String>()
                }
            })
            .collect::<Vec<String>>()
            .join("");
        
        allocations += text_len + 1; // Approximation of allocations
        
        // Parse numbers from the string (more string operations)
        let numbers: Vec<i32> = processed
            .chars()
            .enumerate()
            .filter_map(|(idx, _)| {
                if idx % 100 == 0 {
                    Some(idx as i32)
                } else {
                    None
                }
            })
            .collect();
        
        // Keep some results to prevent optimization
        if i % 100 == 0 {
            result_strings.push(format!("{}_{}", numbers.len(), i));
            allocations += 1;
        }
    }
    
    let duration = start.elapsed();
    
    Json(MicroResponse {
        operations: repetitions,
        duration_ms: duration.as_secs_f64() * 1000.0,
        allocations,
        result: Some(format!("results_{}", result_strings.len())),
    })
}
