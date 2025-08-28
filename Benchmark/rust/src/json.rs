use axum::Json;
use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize, Serialize)]
pub struct Model {
    gender: String,
    id: u32,
    name: String,
    age: u32,
    description: String,
    height: f32,
    weight: f32,
}

pub async fn handler(json: Json<Model>) -> Json<Model> {
    json
}
