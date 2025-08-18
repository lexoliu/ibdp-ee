use axum::{extract::Query, response::Json};
use serde::{Deserialize, Serialize};
use std::time::Instant;
use std::sync::Arc;
use crossbeam_channel::bounded;
use std::thread;

#[derive(Serialize)]
pub struct MesoResponse {
    items_processed: usize,
    duration_ms: f64,
    throughput_ops_sec: f64,
    result: String,
}

#[derive(Deserialize)]
pub struct B1Query {
    items: Option<usize>,
    transform_type: Option<String>,
}

#[derive(Serialize, Deserialize, Clone)]
struct DataItem {
    id: u32,
    name: String,
    values: Vec<f64>,
    metadata: std::collections::HashMap<String, String>,
}

/// B1: Batch processing transformation (CSV/JSON → transform → JSON)
pub async fn b1_batch_transform(Query(params): Query<B1Query>) -> Json<MesoResponse> {
    let item_count = params.items.unwrap_or(1000);
    let transform_type = params.transform_type.unwrap_or_else(|| "json".to_string());
    
    let start = Instant::now();
    
    // Generate input data
    let input_data: Vec<DataItem> = (0..item_count)
        .map(|i| {
            let mut metadata = std::collections::HashMap::new();
            metadata.insert("category".to_string(), format!("cat_{}", i % 10));
            metadata.insert("priority".to_string(), (i % 3).to_string());
            
            DataItem {
                id: i as u32,
                name: format!("item_{}", i),
                values: (0..10).map(|j| (i + j) as f64 * 0.1).collect(),
                metadata,
            }
        })
        .collect();
    
    // Transform data based on type
    let transformed_data: Vec<DataItem> = match transform_type.as_str() {
        "json" => {
            // JSON serialization/deserialization transformation
            input_data
                .into_iter()
                .map(|item| {
                    let json_str = serde_json::to_string(&item).unwrap();
                    let mut deserialized: DataItem = serde_json::from_str(&json_str).unwrap();
                    
                    // Apply transformation
                    deserialized.values = deserialized
                        .values
                        .into_iter()
                        .map(|v| v * 2.0 + 1.0)
                        .collect();
                    
                    deserialized.name = format!("transformed_{}", deserialized.name);
                    deserialized
                })
                .collect()
        }
        "csv" => {
            // CSV-like transformation
            input_data
                .into_iter()
                .map(|mut item| {
                    let csv_line = format!(
                        "{},{},{}",
                        item.id,
                        item.name,
                        item.values
                            .iter()
                            .map(|v| v.to_string())
                            .collect::<Vec<_>>()
                            .join(";")
                    );
                    
                    // Parse back (simulating CSV processing)
                    let parts: Vec<&str> = csv_line.split(',').collect();
                    item.name = format!("csv_{}", parts[1]);
                    item.values = item.values.into_iter().map(|v| v.sqrt()).collect();
                    
                    item
                })
                .collect()
        }
        _ => input_data, // No transformation
    };
    
    let duration = start.elapsed();
    let duration_ms = duration.as_secs_f64() * 1000.0;
    
    Json(MesoResponse {
        items_processed: transformed_data.len(),
        duration_ms,
        throughput_ops_sec: item_count as f64 / duration.as_secs_f64(),
        result: format!(
            "transformed_{}_items_avg_value_{:.2}",
            transformed_data.len(),
            transformed_data
                .iter()
                .map(|item| item.values.iter().sum::<f64>() / item.values.len() as f64)
                .sum::<f64>()
                / transformed_data.len() as f64
        ),
    })
}

#[derive(Deserialize)]
pub struct B2Query {
    produce: Option<usize>,
    chunk: Option<usize>,
    consumers: Option<usize>,
}

/// B2: Multi-producer multi-consumer queue (allocation → reclaim concurrent paths)
pub async fn b2_producer_consumer(Query(params): Query<B2Query>) -> Json<MesoResponse> {
    let total_items = params.produce.unwrap_or(10000);
    let chunk_size = params.chunk.unwrap_or(256);
    let consumer_count = params.consumers.unwrap_or(2);
    
    let start = Instant::now();
    
    // Create bounded channel for backpressure
    let (sender, receiver) = bounded(1000);
    
    let producers = 2;
    let items_per_producer = total_items / producers;
    
    // Spawn producers
    let mut producer_handles = Vec::new();
    for producer_id in 0..producers {
        let tx = sender.clone();
        let handle = thread::spawn(move || {
            for i in 0..items_per_producer {
                let item = WorkItem {
                    id: producer_id * items_per_producer + i,
                    data: (0..chunk_size).map(|j| ((i + j) % 256) as u8).collect(),
                    timestamp: std::time::SystemTime::now(),
                };
                
                if tx.send(item).is_err() {
                    break;
                }
            }
        });
        producer_handles.push(handle);
    }
    
    // Spawn consumers
    let processed_counter = Arc::new(std::sync::atomic::AtomicUsize::new(0));
    let mut consumer_handles = Vec::new();
    
    for _ in 0..consumer_count {
        let rx = receiver.clone();
        let counter = Arc::clone(&processed_counter);
        
        let handle = thread::spawn(move || {
            while let Ok(item) = rx.recv() {
                // Process the item (simulate work)
                let _checksum: usize = item.data.iter().map(|&b| b as usize).sum();
                let _processing_time = std::time::Duration::from_micros(10);
                std::thread::sleep(_processing_time);
                
                counter.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            }
        });
        consumer_handles.push(handle);
    }
    
    // Wait for producers to finish
    drop(sender); // Close the channel
    for handle in producer_handles {
        handle.join().unwrap();
    }
    
    // Wait a bit for consumers to finish processing
    thread::sleep(std::time::Duration::from_millis(100));
    
    let processed_items = processed_counter.load(std::sync::atomic::Ordering::Relaxed);
    let duration = start.elapsed();
    let duration_ms = duration.as_secs_f64() * 1000.0;
    
    Json(MesoResponse {
        items_processed: processed_items,
        duration_ms,
        throughput_ops_sec: processed_items as f64 / duration.as_secs_f64(),
        result: format!("processed_{}_of_{}_items", processed_items, total_items),
    })
}

#[derive(Clone)]
struct WorkItem {
    id: usize,
    data: Vec<u8>,
    timestamp: std::time::SystemTime,
}
