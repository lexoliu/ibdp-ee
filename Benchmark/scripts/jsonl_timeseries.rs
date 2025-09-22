#!/usr/bin/env rust-script
//! ```cargo
//! [dependencies]
//! rayon = "1.10"
//! simd-json = "0.13"
//! time = { version = "0.3.37", features = ["parsing"] }
//! ```

use rayon::iter::ParallelBridge;
use rayon::prelude::*;
use simd_json::{prelude::*, BorrowedValue}; // get(), as_str(), as_f64()
use std::collections::HashMap;
use std::env;
use std::fs::File;
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::path::Path;
use time::format_description::well_known::Rfc3339;
use time::OffsetDateTime;

#[derive(Default, Clone)]
struct Bucket {
    count: u64,
    latency_sum: f64,
    latency_count: u64,
}

#[derive(Copy, Clone)]
enum Metric {
    HttpReq,
    HttpReqDuration,
}

fn main() {
    if let Err(err) = run() {
        eprintln!("jsonl_timeseries: {err}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = env::args().skip(1);
    let input_path = args
        .next()
        .ok_or("usage: jsonl_timeseries <input.jsonl> <output.csv>")?;
    let output_path = args
        .next()
        .ok_or("usage: jsonl_timeseries <input.jsonl> <output.csv>")?;
    if args.next().is_some() {
        return Err("usage: jsonl_timeseries <input.jsonl> <output.csv>".into());
    }

    let input_file = File::open(&input_path)?;
    if let Some(parent) = Path::new(&output_path).parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }
    let output_file = File::create(&output_path)?;

    let reader = BufReader::new(input_file);

    // Stream lines -> parallel processing (no big Vec<String> in memory)
    let buckets: HashMap<i64, Bucket> = reader
        .split(b'\n')
        .par_bridge()
        .filter_map(Result::ok)
        .filter(|b| !b.is_empty()) // fast skip
        .filter_map(parse_line_bytes) // returns (sec, metric, latency)
        .fold(
            HashMap::new,
            |mut acc: HashMap<i64, Bucket>, (sec, metric, latency)| {
                let bucket: &mut Bucket = acc.entry(sec).or_default();
                match metric {
                    Metric::HttpReq => bucket.count += 1,
                    Metric::HttpReqDuration => {
                        if let Some(lat) = latency {
                            bucket.latency_sum += lat;
                            bucket.latency_count += 1;
                        }
                    }
                }
                acc
            },
        )
        .reduce(HashMap::new, |mut acc, m| {
            for (k, v) in m {
                let b = acc.entry(k).or_default();
                b.count += v.count;
                b.latency_sum += v.latency_sum;
                b.latency_count += v.latency_count;
            }
            acc
        });

    let mut writer = BufWriter::new(output_file);
    writeln!(writer, "second,throughput,latency_ms")?;

    if buckets.is_empty() {
        writer.flush()?;
        return Ok(());
    }

    // Use the smallest observed second as anchor (relative time = second - anchor)
    let anchor = *buckets.keys().min().unwrap();

    let mut seconds: Vec<i64> = buckets.keys().copied().collect();
    seconds.sort_unstable();

    for second in seconds {
        if let Some(bucket) = buckets.get(&second) {
            let relative = second - anchor;
            let avg_latency = if bucket.latency_count > 0 {
                bucket.latency_sum / bucket.latency_count as f64
            } else {
                0.0
            };
            writeln!(writer, "{},{},{:.4}", relative, bucket.count, avg_latency)?;
        }
    }

    writer.flush()?;
    Ok(())
}

/// Parse one JSONL line from raw bytes (mutated in-place by simd-json)
fn parse_line_bytes(mut bytes: Vec<u8>) -> Option<(i64, Metric, Option<f64>)> {
    // Trim leading/trailing ASCII whitespace (incl. potential '\r')
    let mut start = 0usize;
    let mut end = bytes.len();
    while start < end && bytes[start].is_ascii_whitespace() {
        start += 1;
    }
    while end > start && bytes[end - 1].is_ascii_whitespace() {
        end -= 1;
    }
    if start >= end {
        return None;
    }
    let slice = &mut bytes[start..end];

    // Parse to BorrowedValue (zero-copy)
    let value: BorrowedValue = simd_json::to_borrowed_value(slice).ok()?;

    // type == "Point"
    let typ = value.get("type")?.as_str()?;
    if typ != "Point" {
        return None;
    }

    // metric
    let metric = match value.get("metric")?.as_str()? {
        "http_reqs" => Metric::HttpReq,
        "http_req_duration" => Metric::HttpReqDuration,
        _ => return None,
    };

    // data.time -> sec, data.value -> latency (ms)
    let data = value.get("data")?;
    let sec = parse_k6_time_to_sec(data.get("time")?)?;
    if sec < 0 {
        return None; // keep original behavior: ignore negative timestamps
    }
    let latency = data.get("value").and_then(|v| v.as_f64());

    Some((sec, metric, latency))
}

/// Convert time field to epoch seconds.
/// Accepts numeric values (ns/ms/s heuristics) or RFC3339 strings.
fn parse_k6_time_to_sec(value: &BorrowedValue) -> Option<i64> {
    if let Some(f) = value.as_f64() {
        return parse_numeric_time(f);
    }
    if let Some(s) = value.as_str() {
        return parse_iso_time(s);
    }
    None
}

fn parse_numeric_time(v: f64) -> Option<i64> {
    if !v.is_finite() {
        return None;
    }
    // Heuristic:
    // - >1e12 => ns
    // - 1e6..1e9 => ms
    // - else => seconds
    if v > 1_000_000_000_000.0 {
        Some((v / 1_000_000_000.0) as i64)
    } else if v > 1_000_000.0 && v < 1_000_000_000.0 {
        Some((v / 1_000.0) as i64)
    } else {
        Some(v as i64)
    }
}

fn parse_iso_time(text: &str) -> Option<i64> {
    OffsetDateTime::parse(text, &Rfc3339)
        .ok()
        .map(|dt| dt.unix_timestamp())
}
