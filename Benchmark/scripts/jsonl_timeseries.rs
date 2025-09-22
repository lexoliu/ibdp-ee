#!/usr/bin/env rust-script
//! ```cargo
//! [dependencies]
//! rayon = "1.10"
//! serde = { version = "1.0", features = ["derive"] }
//! simd-json = "0.13"
//! time = { version = "0.3.37", features = ["parsing"] }
//! ```

use rayon::prelude::*;
use serde::Deserialize;
use simd_json::BorrowedValue;
use std::collections::HashMap;
use std::env;
use std::fs::File;
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::path::Path;
use time::format_description::well_known::Rfc3339;
use time::OffsetDateTime;

/// A single data point in the JSONL file.
#[derive(Deserialize)]
struct Point<'a> {
    #[serde(rename = "type")]
    typ: &'a str,
    metric: &'a str,
    data: Data<'a>,
}

/// `data` object inside the point
#[derive(Deserialize)]
struct Data<'a> {
    time: BorrowedValue<'a>, // may be number or string
    #[serde(default)]
    value: Option<f64>,
}

/// Aggregation bucket
#[derive(Default, Clone)]
struct Bucket {
    count: u64,
    latency_sum: f64,
    latency_count: u64,
}

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
    let lines: Vec<String> = reader.lines().filter_map(Result::ok).collect();

    // Parallel parse + local aggregation per thread
    let buckets: HashMap<i64, Bucket> = lines
        .par_iter()
        .filter_map(|line| parse_line(line))
        .fold(HashMap::new, |mut acc, (sec, metric, latency)| {
            let bucket = acc.entry(sec).or_default();
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
        })
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

/// Parse one JSONL line into (second, metric, latency)
fn parse_line(line: &str) -> Option<(i64, Metric, Option<f64>)> {
    // simd-json requires &mut str
    let mut line_mut = line.to_owned();
    let point: Point = simd_json::from_str(&mut line_mut).ok()?;
    if point.typ != "Point" {
        return None;
    }

    let sec = parse_k6_time_to_sec(&point.data.time)?;
    let metric = match point.metric {
        "http_reqs" => Metric::HttpReq,
        "http_req_duration" => Metric::HttpReqDuration,
        _ => return None,
    };

    Some((sec, metric, point.data.value))
}

/// Convert k6 time field to seconds
fn parse_k6_time_to_sec(value: &BorrowedValue<'_>) -> Option<i64> {
    match value {
        BorrowedValue::F64(v) => parse_numeric_time(*v),
        BorrowedValue::U64(v) => Some(*v as i64),
        BorrowedValue::I64(v) => Some(*v),
        BorrowedValue::String(s) => parse_iso_time(s.as_str()),
        _ => None,
    }
}

fn parse_numeric_time(v: f64) -> Option<i64> {
    if !v.is_finite() {
        return None;
    }
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
        .map(|dt| dt.unix_timestamp())
        .ok()
}
