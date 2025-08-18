use axum::{
    routing::get, Router,
};
use std::{collections::HashMap, sync::Arc};
use tokio::net::TcpListener;

mod c0_pure_compute;
mod micro_tests;
mod meso_tests;
mod macro_tests;

use c0_pure_compute::*;
use micro_tests::*;
use meso_tests::*;
use macro_tests::*;

#[derive(Clone)]
pub struct AppState {
    // Shared state for all benchmarks
    data_store: Arc<parking_lot::Mutex<HashMap<String, Vec<u8>>>>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            data_store: Arc::new(parking_lot::Mutex::new(HashMap::new())),
        }
    }
}

#[tokio::main]
async fn main() {
    let state = AppState::default();
    
    let app = Router::new()
        // C0 Pure Compute (Negative Control)
        .route("/compute/c0a", get(c0a_vector_dot_product))
        .route("/compute/c0b", get(c0b_vectorizable_vs_branchy))
        .route("/compute/c0c", get(c0c_fft_convolution))
        .route("/compute/c0d", get(c0d_allocation_strategy))
        
        // Micro Tests (Memory Behavior Isolation)
        .route("/compute/a1", get(a1_short_lived_burst))
        .route("/compute/a2", get(a2_long_lived_tidal))
        .route("/compute/a3", get(a3_graph_traversal))
        .route("/compute/a4", get(a4_string_operations))
        
        // Meso Tests (Medium Scale)
        .route("/meso/b1", get(b1_batch_transform))
        .route("/meso/b2", get(b2_producer_consumer))
        
        // Macro Tests (End-to-End Web)
        .route("/echo", get(c1_echo))
        .route("/static/*path", get(c2_static_file))
        .route("/json", get(c3_json_api))
        .route("/template", get(c4_template_render))
        .route("/db/user", get(c5_db_query))
        
        // Health check
        .route("/health", get(health_check))
        .with_state(state);

    let listener = TcpListener::bind("0.0.0.0:8080").await.unwrap();
    println!("Rust benchmark server started on http://0.0.0.0:8080");
    
    axum::serve(listener, app).await.unwrap();
}

async fn health_check() -> &'static str {
    "OK"
}
