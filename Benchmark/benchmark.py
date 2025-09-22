#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run k6 workloads against an already running language service."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
import re
from typing import Callable, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent
K6_DIR = ROOT / "k6"
RESULTS_ROOT = ROOT / "results"
JSONL_SCRIPT_PATH = ROOT / "scripts" / "jsonl_timeseries.rs"
_RUST_SCRIPT_CMD: list[str] | None = None


def _locate_rust_script() -> list[str]:
    global _RUST_SCRIPT_CMD
    if _RUST_SCRIPT_CMD is not None:
        return _RUST_SCRIPT_CMD

    for binary in ("rust-script", "cargo-script"):
        path = shutil.which(binary)
        if path:
            _RUST_SCRIPT_CMD = [path]
            return _RUST_SCRIPT_CMD

    cargo = shutil.which("cargo")
    if cargo is None:
        fallback = Path.home() / ".cargo" / "bin" / "cargo"
        if fallback.exists():
            cargo = str(fallback)
    if cargo is not None:
        probe = subprocess.run(
            [cargo, "script", "-V"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if probe.returncode == 0:
            _RUST_SCRIPT_CMD = [cargo, "script"]
            return _RUST_SCRIPT_CMD

    raise RuntimeError(
        "cargo-script / rust-script not found. Install via `cargo install cargo-script` or `cargo install rust-script`."
    )


def convert_jsonl_to_csv(jsonl_path: Path, csv_path: Path) -> None:
    if not JSONL_SCRIPT_PATH.exists():
        raise RuntimeError(f"JSONL converter script missing: {JSONL_SCRIPT_PATH}")

    base_cmd = _locate_rust_script()
    if base_cmd[0].endswith("rust-script"):
        cmd = base_cmd + ["-O", str(JSONL_SCRIPT_PATH), "--", str(jsonl_path), str(csv_path)]
    else:
        cmd = base_cmd + ["--release", str(JSONL_SCRIPT_PATH), "--", str(jsonl_path), str(csv_path)]

    proc = subprocess.run(cmd, cwd=str(ROOT))
    if proc.returncode != 0:
        raise RuntimeError(
            f"jsonl_timeseries script failed with exit code {proc.returncode}"
        )

TEST_SCRIPTS = {
    "prime": K6_DIR / "prime.js",
    "light": K6_DIR / "light.js",
    "kv": K6_DIR / "kv.js",
}

DEFAULT_TEST_ORDER = ["prime", "light", "kv"]

MODE_DEFAULTS = {
    "debug": {"duration": "10s", "repeats": 1},
    "normal": {"duration": "10m", "repeats": 3},
}


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
    parser.add_argument("--mode", choices=MODE_DEFAULTS.keys(), default=os.environ.get("MODE", "normal"), help="Select run mode: debug=10s smoke, normal=10m stress")
    parser.add_argument("--vus", type=int, default=int(os.environ.get("VUS", "64")))
    parser.add_argument(
        "--duration",
        default=os.environ.get("DURATION"),
        help="Override test duration (e.g. 30s, 5m). Defaults come from the chosen mode.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=os.environ.get("REPEATS"),
        help="Override how many times to rerun the suite. Defaults come from the chosen mode.",
    )
    parser.add_argument("--keep-raw", action="store_true", default=os.environ.get("KEEP_RAW", "0") == "1")
    parser.add_argument("--output-dir", default=None, help="Custom results directory")
    parser.add_argument("--label", default=None, help="Optional run label printed in summary")
    parser.add_argument("--wait", type=int, default=60, help="Seconds to wait for /echo health (default 60)")
    parser.add_argument(
        "--memory-status-url",
        default=None,
        help="Manager status endpoint to query for memory usage (optional)",
    )
    parser.add_argument(
        "--memory-interval",
        type=float,
        default=1.0,
        help="Sampling interval in seconds when collecting memory (default: 1.0)",
    )
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


def run_k6(
    test: str,
    script: Path,
    base_url: str,
    output_dir: Path,
    vus: int,
    duration: str,
    attempt: int,
    total_attempts: int,
) -> Tuple[Path, Path]:
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

    period = "1s"
    env.setdefault("K6_OUT_JSON_PERIOD", period)

    attempt_note = f" (attempt {attempt}/{total_attempts})" if total_attempts > 1 else ""
    print(f"Running {' '.join(cmd)}{attempt_note} [json period {period}]")
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


def write_memory_csv(samples: List[Tuple[float, float]], csv_path: Path) -> None:
    if not samples:
        return

    buckets: Dict[int, List[float]] = {}
    for elapsed, value in samples:
        if value is None:
            continue
        second = int(elapsed)
        buckets.setdefault(second, []).append(value)

    if not buckets:
        return

    with csv_path.open("w", encoding="utf-8") as handle:
        handle.write("timestamp,memory_mb\n")
        for second in sorted(buckets.keys()):
            values = buckets[second]
            avg = sum(values) / len(values)
            handle.write(f"{second},{avg:.4f}\n")


class MemorySampler:
    def __init__(self, probe: Callable[[], float | None], interval: float = 1.0) -> None:
        self._probe = probe
        self._interval = interval
        self._stop = threading.Event()
        self._samples: List[Tuple[float, float | None]] = []
        self._thread: threading.Thread | None = None
        self._start_time: float = 0.0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> List[Tuple[float, float]]:
        self._stop.set()
        if self._thread:
            self._thread.join()
        samples = [(elapsed, value) for elapsed, value in self._samples if value is not None]
        self._samples.clear()
        self._stop.clear()
        return samples

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                value = self._probe()
            except Exception:
                value = None
            elapsed = time.time() - self._start_time
            self._samples.append((elapsed, value))
            self._stop.wait(self._interval)


def run_benchmark(
    language: str,
    base_url: str,
    tests: List[str] | None = None,
    *,
    mode: str = "normal",
    vus: int = 64,
    duration_override: str | None = None,
    repeats_override: int | None = None,
    keep_raw: bool = False,
    output_dir: Path | None = None,
    label: str | None = None,
    wait: int = 60,
    memory_probe: Callable[[], float | None] | None = None,
    memory_interval: float = 1.0,
) -> Tuple[Path, Dict[str, Dict[str, float]]]:
    tests = tests or list(DEFAULT_TEST_ORDER)
    mode_defaults = MODE_DEFAULTS[mode]

    raw_duration = duration_override or mode_defaults["duration"]
    duration = raw_duration.strip()
    if not duration:
        duration = mode_defaults["duration"]

    repeats_arg = repeats_override
    try:
        repeats = mode_defaults["repeats"] if repeats_arg is None else int(repeats_arg)
    except (TypeError, ValueError) as exc:
        raise ValueError("Repeat override must be an integer") from exc
    if repeats < 1:
        raise ValueError("Repeat count must be at least 1")

    run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    if output_dir is None:
        output_dir = RESULTS_ROOT / language / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"Mode: {mode} | duration: {duration} | repeats: {repeats} | "
        f"vus: {vus}"
    )
    print(f"Writing artifacts to {output_dir}")

    print(f"Waiting for service at {base_url} ...")
    if not wait_for_service(base_url, wait):
        raise RuntimeError("Service not reachable via /echo")

    summary: Dict[str, Dict[str, float]] = {}

    for test in tests:
        script = TEST_SCRIPTS[test]
        if not script.exists():
            raise FileNotFoundError(f"k6 script missing: {script}")

        final_json_path: Path | None = None
        final_summary_path: Path | None = None
        sampler: MemorySampler | None = None

        print(f"\n--- Running {test} ---")
        if memory_probe is not None:
            sampler = MemorySampler(memory_probe, interval=memory_interval)
            sampler.start()
        for attempt in range(1, repeats + 1):
            json_path, summary_path = run_k6(
                test,
                script,
                base_url,
                output_dir,
                vus,
                duration,
                attempt,
                repeats,
            )
            final_json_path = json_path
            final_summary_path = summary_path

        memory_samples: List[Tuple[float, float]] = []
        if sampler is not None:
            memory_samples = sampler.stop()

        if not final_summary_path or not final_json_path:
            raise RuntimeError("Expected k6 outputs were not produced")

        summary[test] = parse_summary(final_summary_path)

        convert_jsonl_to_csv(final_json_path, output_dir / f"{test}_timeseries.csv")

        if memory_samples:
            write_memory_csv(memory_samples, output_dir / f"{test}_memory.csv")

        if not keep_raw:
            final_json_path.unlink(missing_ok=True)
            final_summary_path.unlink(missing_ok=True)

    result_payload = {
        "language": language,
        "label": label or language,
        "base_url": base_url,
        "vus": vus,
        "duration": duration,
        "mode": mode,
        "repeats": repeats,
        "run_id": run_id,
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
    return output_dir, summary


def main() -> int:
    args = parse_args()

    memory_probe: Callable[[], float | None] | None = None
    if args.memory_status_url:
        def _memory_probe() -> float | None:
            try:
                with urllib.request.urlopen(args.memory_status_url, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except Exception:
                return None
            meta = payload.get("meta")
            if isinstance(meta, dict):
                value = meta.get("memory_mb")
                if isinstance(value, (int, float)):
                    return float(value)
            return None

        memory_probe = _memory_probe

    try:
        run_benchmark(
            args.language,
            args.base_url,
            args.tests,
            mode=args.mode,
            vus=args.vus,
            duration_override=args.duration,
            repeats_override=args.repeats,
            keep_raw=args.keep_raw,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            label=args.label,
            wait=args.wait,
            memory_probe=memory_probe,
            memory_interval=args.memory_interval,
        )
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
TARGET_TIMESERIES_SAMPLES = 600


_DURATION_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)(?P<unit>ms|s|m|h)")


def parse_duration_seconds(duration: str) -> float:
    total = 0.0
    for match in _DURATION_RE.finditer(duration.lower()):
        value = float(match.group("value"))
        unit = match.group("unit")
        if unit == "ms":
            total += value / 1000.0
        elif unit == "s":
            total += value
        elif unit == "m":
            total += value * 60.0
        elif unit == "h":
            total += value * 3600.0
    return total
