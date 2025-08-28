use axum::body::Bytes;

pub async fn handler(input: Bytes) -> Bytes {
    input
}
