#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run k6 workloads against an already running language service."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
K6_DIR = ROOT / "k6"
RESULTS_ROOT = ROOT / "results"

TEST_SCRIPTS = {
    "prime": K6_DIR / "prime.js",
    "light": K6_DIR / "light.js",
    "kv": K6_DIR / "kv.js",
}

DEFAULT_TEST_ORDER = ["prime", "light", "kv"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run k6 suites against a service")
    parser.add_argument("language", help="Label for this run, e.g. java", type=str)
    parser.add_argument(
        "--tests",
        nargs="+",
        default=DEFAULT_TEST_ORDER,
        choices=TEST_SCRIPTS.keys(),
        help="Subset of tests to run",
    )
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--vus", type=int, default=int(os.environ.get("VUS", "64")))
    parser.add_argument("--duration", default=os.environ.get("DURATION", "60s"))
    parser.add_argument("--keep-raw", action="store_true", default=os.environ.get("KEEP_RAW", "0") == "1")
    parser.add_argument("--output-dir", default=None, help="Custom results directory")
    parser.add_argument("--label", default=None, help="Optional run label printed in summary")
    parser.add_argument("--wait", type=int, default=60, help="Seconds to wait for /echo health (default 60)")
    return parser.parse_args()


def wait_for_service(base_url: str, timeout: int) -> bool:
    url = base_url.rstrip("/") + "/echo"
    payload = b"ok"
    headers = {"Content-Type": "text/plain"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=3):
                return True
        except urllib.error.URLError:
            time.sleep(1)
    return False


def run_k6(test: str, script: Path, base_url: str, output_dir: Path, vus: int, duration: str) -> Tuple[Path, Path]:
    json_path = output_dir / f"{test}.jsonl"
    summary_path = output_dir / f"{test}_summary.json"

    cmd = [
        "k6",
        "run",
        "--vus",
        str(vus),
        "--duration",
        duration,
        "--summary-export",
        str(summary_path),
        "--out",
        f"json={json_path}",
        str(script),
    ]

    env = os.environ.copy()
    env.setdefault("BASE_URL", base_url)
    env.setdefault("K6_BASE_URL", base_url)

    print(f"Running {' '.join(cmd)}")
    proc = subprocess.run(cmd, env=env)
    if proc.returncode not in (0, 99):
        raise RuntimeError(f"k6 failed on {test} (exit {proc.returncode})")
    if proc.returncode == 99:
        print(f"⚠️  k6 thresholds breached for {test}, continuing")

    return json_path, summary_path


def parse_summary(summary_path: Path) -> Dict[str, float]:
    data = json.loads(summary_path.read_text())
    metrics = data.get("metrics", {})

    def metric_value(metric: str, key: str) -> float:
        return float(metrics.get(metric, {}).get("values", {}).get(key, 0.0))

    return {
        "http_reqs": metric_value("http_reqs", "count"),
        "throughput": metric_value("http_reqs", "rate"),
        "latency_avg": metric_value("http_req_duration", "avg"),
        "latency_p95": metric_value("http_req_duration", "p(95)"),
        "latency_p99": metric_value("http_req_duration", "p(99)"),
    }


def parse_timeseries(jsonl_path: Path) -> List[Tuple[int, int, float]]:
    series: Dict[int, Dict[str, float]] = {}

    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                node = json.loads(line)
            except json.JSONDecodeError:
                continue
            if node.get("type") != "Point":
                continue

            metric = node.get("metric")
            data = node.get("data", {})
            sec = _parse_k6_time_to_sec(data.get("time"))
            if sec < 0:
                continue
            bucket = series.setdefault(sec, {"count": 0, "lat_sum": 0.0, "lat_cnt": 0})
            if metric == "http_reqs":
                bucket["count"] += 1
            elif metric == "http_req_duration":
                try:
                    value = float(data.get("value", 0.0))
                except (TypeError, ValueError):
                    continue
                bucket["lat_sum"] += value
                bucket["lat_cnt"] += 1

    if not series:
        return []

    anchor = min(series.keys())
    rows: List[Tuple[int, int, float]] = []
    for sec in sorted(series.keys()):
        bucket = series[sec]
        latency = bucket["lat_sum"] / bucket["lat_cnt"] if bucket["lat_cnt"] else 0.0
        rows.append((sec - anchor, int(bucket["count"]), latency))
    return rows


def _parse_k6_time_to_sec(raw_time) -> int:
    if isinstance(raw_time, (int, float)):
        value = float(raw_time)
        if value > 1e12:
            return int(value / 1_000_000_000)
        if 1e6 < value < 1e9:
            return int(value / 1_000)
        return int(value)
    if isinstance(raw_time, str):
        text = raw_time.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return int(datetime.fromisoformat(text).timestamp())
        except ValueError:
            return -1
    return -1


def write_timeseries_csv(rows: List[Tuple[int, int, float]], csv_path: Path) -> None:
    with csv_path.open("w", encoding="utf-8") as handle:
        handle.write("second,throughput,latency_ms\n")
        for second, count, latency in rows:
            handle.write(f"{second},{count},{latency:.4f}\n")


def plot_timeseries(rows: List[Tuple[int, int, float]], png_path: Path, title: str) -> None:
    if not rows:
        return
    seconds = [row[0] for row in rows]
    throughput = [row[1] for row in rows]
    latency = [row[2] for row in rows]

    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.plot(seconds, throughput, color="#1f77b4", label="Throughput (req/s)")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Requests/sec", color="#1f77b4")
    ax1.tick_params(axis='y', labelcolor="#1f77b4")
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(seconds, latency, color="#ff7f0e", label="Latency (ms)")
    ax2.set_ylabel("Latency (ms)", color="#ff7f0e")
    ax2.tick_params(axis='y', labelcolor="#ff7f0e")

    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(png_path, dpi=160)
    plt.close(fig)


def main() -> int:
    args = parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else RESULTS_ROOT / f"{args.language}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Waiting for service at {args.base_url} ...")
    if not wait_for_service(args.base_url, args.wait):
        print("Service not reachable via /echo", file=sys.stderr)
        return 1

    summary: Dict[str, Dict[str, float]] = {}

    for test in args.tests:
        script = TEST_SCRIPTS[test]
        if not script.exists():
            raise FileNotFoundError(f"k6 script missing: {script}")

        json_path, summary_path = run_k6(test, script, args.base_url, output_dir, args.vus, args.duration)
        summary[test] = parse_summary(summary_path)

        rows = parse_timeseries(json_path)
        write_timeseries_csv(rows, output_dir / f"{test}_timeseries.csv")
        plot_timeseries(rows, output_dir / f"{test}_timeseries.png", f"{args.language.upper()} - {test}")

        if not args.keep_raw:
            json_path.unlink(missing_ok=True)
            summary_path.unlink(missing_ok=True)

    result_payload = {
        "language": args.language,
        "label": args.label or args.language,
        "base_url": args.base_url,
        "vus": args.vus,
        "duration": args.duration,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "summary": summary,
    }
    (output_dir / "results.json").write_text(json.dumps(result_payload, indent=2))

    print("\n=== Summary ===")
    for test, stats in summary.items():
        print(
            f"{test}: throughput≈{stats['throughput']:.2f} req/s, "
            f"avg latency≈{stats['latency_avg']:.2f} ms, p95≈{stats['latency_p95']:.2f} ms"
        )

    print(f"\nArtifacts written to: {output_dir}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
