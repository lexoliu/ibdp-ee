use axum::Json;
use serde_json::Value;
use serde_xml_rs::to_string;

pub async fn handler(Json(input): Json<Value>) -> String {
    to_string(&input).unwrap()
}
