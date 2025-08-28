mod checksum;
mod echo;
mod is_prime;
mod json;
mod json2xml;
use axum::{Router, routing::*};

use crate::kv::Engine;
mod kv;
mod template;
#[tokio::main]
async fn main() {
    let app = router();
    let listener = tokio::net::TcpListener::bind("127.0.0.1:3000")
        .await
        .unwrap();
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
        .with_state(Engine::new())
}
