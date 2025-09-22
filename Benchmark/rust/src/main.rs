mod checksum;
mod echo;
mod is_prime;
mod json;
mod json2xml;
use std::env;

use axum::{routing::*, Router};

use crate::kv::Engine;
mod kv;
mod template;

fn logging_enabled() -> bool {
    match env::var("SERVER_LOG") {
        Ok(value) => {
            let text = value.trim().to_ascii_lowercase();
            if text.is_empty() {
                return false;
            }
            !matches!(text.as_str(), "0" | "false" | "off" | "no")
        }
        Err(_) => false,
    }
}

#[tokio::main]
async fn main() {
    let host = env::var("SERVER_HOST").unwrap_or_else(|_| "0.0.0.0".into());
    let port = env::var("SERVER_PORT").unwrap_or_else(|_| "8080".into());
    let addr = format!("{}:{}", host, port);

    let app = router();
    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    if logging_enabled() {
        println!("listening on http://{}", addr);
    }
    axum::serve(listener, app).await.unwrap();
}

fn router() -> Router {
    Router::new()
        .route("/is_prime", post(is_prime::handler))
        .route("/echo", post(echo::handler))
        .route("/json2xml", post(json2xml::handler))
        .route("/json", post(json::handler))
        .route(
            "/template",
            post(template::handler).with_state(template::Engine::new()),
        )
        .nest("/kv", kv_router())
}

fn kv_router() -> Router {
    Router::new()
        .route("/get/{id}", get(kv::get))
        .route("/set/{id}", post(kv::post))
        .route("/delete/{id}", delete(kv::delete))
        .route("/stats", get(kv::stats))
        .with_state(Engine::new())
}
