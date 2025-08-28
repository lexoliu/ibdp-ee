use axum::body::Bytes;

fn checksum(data: &[u8]) -> u32 {
    data.iter()
        .fold(0u32, |acc, &byte| acc.wrapping_add(byte as u32))
}

pub async fn handler(data: Bytes) -> String {
    let sum = checksum(&data);
    format!("{:08x}", sum)
}
