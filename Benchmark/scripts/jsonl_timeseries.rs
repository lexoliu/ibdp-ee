#!/usr/bin/env rust-script
//! ```cargo
//! [dependencies]
//! serde_json = "1.0.143"
//! time = { version = "0.3.37", features = ["parsing"] }
//! ```
//!

use serde_json::Value;
use std::collections::HashMap;
use std::env;
use std::fs::File;
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::path::Path;
use time::format_description::well_known::Rfc3339;
use time::OffsetDateTime;

#[derive(Default)]
struct Bucket {
    count: u64,
    latency_sum: f64,
    latency_count: u64,
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
    let mut writer = BufWriter::new(output_file);

    let mut buckets: HashMap<i64, Bucket> = HashMap::new();
    let mut min_second: Option<i64> = None;

    for line_result in reader.lines() {
        let line = match line_result {
            Ok(line) => line,
            Err(err) => {
                eprintln!("jsonl_timeseries: failed to read line: {err}");
                continue;
            }
        };

        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        let node: Value = match serde_json::from_str(trimmed) {
            Ok(value) => value,
            Err(_) => continue,
        };

        if node
            .get("type")
            .and_then(Value::as_str)
            .map(|kind| kind != "Point")
            .unwrap_or(true)
        {
            continue;
        }

        let metric = match node.get("metric").and_then(Value::as_str) {
            Some(metric) => metric,
            None => continue,
        };

        let data = match node.get("data").and_then(Value::as_object) {
            Some(data) => data,
            None => continue,
        };

        let sec = match parse_k6_time_to_sec(data.get("time")) {
            Some(sec) if sec >= 0 => sec,
            _ => continue,
        };

        let bucket = buckets.entry(sec).or_default();
        match metric {
            "http_reqs" => {
                bucket.count += 1;
            }
            "http_req_duration" => {
                if let Some(value) = data.get("value").and_then(extract_f64) {
                    bucket.latency_sum += value;
                    bucket.latency_count += 1;
                }
            }
            _ => {}
        }

        min_second = Some(min_second.map_or(sec, |current| current.min(sec)));
    }

    writeln!(writer, "second,throughput,latency_ms")?;

    let Some(anchor) = min_second else {
        writer.flush()?;
        return Ok(());
    };

    let mut seconds: Vec<i64> = buckets.keys().copied().collect();
    seconds.sort_unstable();

    for second in seconds {
        if let Some(bucket) = buckets.get(&second) {
            let relative = second - anchor;
            let average_latency = if bucket.latency_count > 0 {
                bucket.latency_sum / bucket.latency_count as f64
            } else {
                0.0
            };
            writeln!(
                writer,
                "{},{},{}",
                relative,
                bucket.count,
                format!("{average_latency:.4}")
            )?;
        }
    }

    writer.flush()?;
    Ok(())
}

fn extract_f64(value: &Value) -> Option<f64> {
    match value {
        Value::Number(number) => number.as_f64(),
        Value::String(text) => text.parse::<f64>().ok(),
        _ => None,
    }
}

fn parse_k6_time_to_sec(raw: Option<&Value>) -> Option<i64> {
    let value = raw?;
    match value {
        Value::Number(number) => number.as_f64().and_then(parse_numeric_time),
        Value::String(text) => parse_iso_time(text),
        _ => None,
    }
}

fn parse_numeric_time(value: f64) -> Option<i64> {
    if !value.is_finite() {
        return None;
    }

    if value > 1_000_000_000_000.0 {
        Some((value / 1_000_000_000.0) as i64)
    } else if value > 1_000_000.0 && value < 1_000_000_000.0 {
        Some((value / 1_000.0) as i64)
    } else {
        Some(value as i64)
    }
}

fn parse_iso_time(text: &str) -> Option<i64> {
    if text.is_empty() {
        return None;
    }

    OffsetDateTime::parse(text, &Rfc3339)
        .map(|dt| dt.unix_timestamp())
        .ok()
}
