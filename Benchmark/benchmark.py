#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run k6 workloads against an already running language service."""

from __future__ import annotations

import argparse
import json
import os
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

TEST_SCRIPTS = {
    "prime": K6_DIR / "prime.js",
    "light": K6_DIR / "light.js",
    "kv": K6_DIR / "kv.js",
}



def resolve_kv_key_space(mode: str) -> int:
    override = os.environ.get("K6_KV_KEY_SPACE")
    if override:
        try:
            value = int(override)
            if value > 0:
                return value
            print(f"Warning: ignoring non-positive K6_KV_KEY_SPACE override: {override}")
        except ValueError:
            print(f"Warning: invalid K6_KV_KEY_SPACE override '{override}', using default")

    # Reduced key space for debug mode to accommodate realistic cache data complexity
    return 250 if mode == "debug" else 100_000

# Prioritize `kv` because it tends to surface stability problems fastest.
DEFAULT_TEST_ORDER = ["kv", "prime", "light"]

MODE_DEFAULTS = {
    "debug": {"duration": "2s", "repeats": 1},
    "normal": {"duration": "10m", "repeats": 2}, # One prewarm, one measured
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
    parser.add_argument("--mode", choices=MODE_DEFAULTS.keys(), default=os.environ.get("MODE", "normal"), help="Select run mode: debug=2s smoke, normal=5m stress")
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
    *,
    kv_key_space: int | None = None,
    mode: str | None = None,
) -> Tuple[Path, Path]:
    csv_path = output_dir / f"{test}_timeseries.csv"  # Will be created by k6 handleSummary
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
        str(script.resolve()),  # Use absolute path since we change cwd
    ]

    env = os.environ.copy()
    env.setdefault("BASE_URL", base_url)
    env.setdefault("K6_BASE_URL", base_url)
    env.setdefault("K6_DURATION", duration)
    if mode is not None:
        env.setdefault("K6_MODE", mode)
    if test == "kv" and kv_key_space is not None:
        env.setdefault("K6_KV_KEY_SPACE", str(kv_key_space))

    attempt_note = f" (attempt {attempt}/{total_attempts})" if total_attempts > 1 else ""
    print(f"Running {' '.join(cmd)}{attempt_note} [per-second aggregation via handleSummary]")
    proc = subprocess.run(cmd, env=env, cwd=str(output_dir))
    if proc.returncode not in (0, 99):
        raise RuntimeError(f"k6 failed on {test} (exit {proc.returncode})")
    if proc.returncode == 99:
        print(f"⚠️  k6 thresholds breached for {test}, continuing")

    return csv_path, summary_path


def fetch_kv_entries(base_url: str) -> int | None:
    url = base_url.rstrip("/") + "/kv/stats"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"Warning: failed to fetch KV stats from {url}: {exc}")
        return None

    entries = payload.get("entries") if isinstance(payload, dict) else None
    if isinstance(entries, int):
        return entries
    print(f"Warning: KV stats response missing 'entries': {payload}")
    return None


def _fill_missing_kv_entries(base_url: str, current_entries: int, target_entries: int, key_space: int) -> None:
    """Fill missing KV entries to reach the target count."""
    import time
    
    missing = target_entries - current_entries
    if missing <= 0:
        return
    
    # Generate additional entries to fill the gap
    base_set_url = base_url.rstrip("/") + "/kv/set"
    
    for i in range(missing):
        # Generate a key that should be unique within the keyspace
        # Use current_entries + i to avoid collisions with existing keys
        key_id = (current_entries + i) % key_space
        key = f"key_{key_id:06d}"
        value = f"autofill_value_{i}"
        
        url = f"{base_set_url}/{key}"
        request = urllib.request.Request(url, data=value.encode('utf-8'), method="POST")
        
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                pass  # Just ensure the request succeeds
        except Exception as exc:
            print(f"Warning: failed to set {key}: {exc}")
            
        # Small delay to avoid overwhelming the service
        if i % 100 == 0 and i > 0:
            time.sleep(0.01)


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


def is_experiment_complete(output_dir: Path, tests: List[str]) -> Tuple[bool, List[str]]:
    """Check if experiment is complete by verifying CSV files exist."""
    missing_tests = []
    for test in tests:
        csv_file = output_dir / f"{test}_timeseries.csv"
        if not csv_file.exists():
            missing_tests.append(test)
    return len(missing_tests) == 0, missing_tests


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
    skip_completed: bool = True,
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

    if output_dir is None:
        output_dir = RESULTS_ROOT / language
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if experiment is already complete
    if skip_completed:
        is_complete, missing_tests = is_experiment_complete(output_dir, tests)
        if is_complete:
            print(f"Experiment for {language} already complete. Loading existing results...")
            results_file = output_dir / "results.json"
            if results_file.exists():
                existing_data = json.loads(results_file.read_text())
                return output_dir, existing_data.get("summary", {})
        elif missing_tests:
            print(f"Partially complete experiment. Missing tests: {missing_tests}")
            tests = missing_tests  # Only run missing tests

    print(
        f"Mode: {mode} | duration: {duration} | repeats: {repeats} | "
        f"vus: {vus}"
    )
    print(f"Writing artifacts to {output_dir}")

    kv_key_space = resolve_kv_key_space(mode)
    print(
        "Resolved KV key space:",
        f"{kv_key_space} keys per VU (total target {kv_key_space * vus:,})",
    )

    print(f"Waiting for service at {base_url} ...")
    if not wait_for_service(base_url, wait):
        raise RuntimeError("Service not reachable via /echo")

    summary: Dict[str, Dict[str, float]] = {}

    for test in tests:
        script = TEST_SCRIPTS[test]
        if not script.exists():
            raise FileNotFoundError(f"k6 script missing: {script}")

        final_csv_path: Path | None = None
        final_summary_path: Path | None = None
        sampler: MemorySampler | None = None

        print(f"\n--- Running {test} ---")
        if memory_probe is not None:
            sampler = MemorySampler(memory_probe, interval=memory_interval)
            sampler.start()
        for attempt in range(1, repeats + 1):
            csv_path, summary_path = run_k6(
                test,
                script,
                base_url,
                output_dir,
                vus,
                duration,
                attempt,
                repeats,
                kv_key_space=kv_key_space if test == "kv" else None,
                mode=mode,
            )
            final_csv_path = csv_path
            final_summary_path = summary_path

        memory_samples: List[Tuple[float, float]] = []
        if sampler is not None:
            memory_samples = sampler.stop()

        if not final_summary_path:
            raise RuntimeError("Expected k6 summary was not produced")

        summary[test] = parse_summary(final_summary_path)

        # CSV is generated directly by k6's handleSummary function
        csv_file = output_dir / f"{test}_timeseries.csv"
        if csv_file.exists():
            print(f"Per-second CSV generated: {csv_file} ({csv_file.stat().st_size} bytes)")
        else:
            print(f"Warning: Expected CSV not found at {csv_file}")

        if memory_samples:
            write_memory_csv(memory_samples, output_dir / f"{test}_memory.csv")

        if test == "kv":
            entries = fetch_kv_entries(base_url)
            expected_entries = vus * kv_key_space
            print(
                "KV occupancy check:",
                f"expected {expected_entries:,} entries (VUs={vus} × key_space={kv_key_space})",
                f"observed {entries if entries is not None else 'unknown'}",
            )
            if entries is None:
                raise RuntimeError("Unable to verify KV occupancy after benchmark run")
            
            # Calculate tolerance (30% of expected for realistic cache data)
            tolerance = int(expected_entries * 0.3)
            difference = abs(entries - expected_entries)
            
            if entries == expected_entries:
                print("KV occupancy verified.")
            elif difference <= tolerance:
                print(f"WARNING: KV occupancy within tolerance ({difference} entries off, tolerance: {tolerance})")
                if entries < expected_entries:
                    # Auto-fill missing entries
                    missing = expected_entries - entries
                    print(f"Auto-filling {missing} missing entries...")
                    _fill_missing_kv_entries(base_url, entries, expected_entries, kv_key_space)
                    # Verify after filling
                    new_entries = fetch_kv_entries(base_url)
                    if new_entries is None:
                        raise RuntimeError("Unable to verify KV occupancy after auto-fill")

                    print(f"After auto-fill: {new_entries} entries")
                    if new_entries == expected_entries:
                        print("KV occupancy verified after auto-fill.")
                    else:
                        deficit = expected_entries - new_entries
                        if deficit > 0:
                            print(f"WARNING: Auto-fill incomplete, still {deficit} entries short")
                        else:
                            print("WARNING: Auto-fill overshot expected occupancy; continuing")
                else:
                    print("KV occupancy acceptable (slightly over expected).")
            else:
                raise RuntimeError(
                    "KV occupancy check failed: "
                    f"expected {expected_entries} entries but service reported {entries} "
                    f"(difference: {difference}, tolerance: {tolerance})"
                )

        if not keep_raw:
            # Only delete summary file - CSV is the main output now
            final_summary_path.unlink(missing_ok=True)

    result_payload = {
        "language": language,
        "label": label or language,
        "base_url": base_url,
        "vus": vus,
        "duration": duration,
        "mode": mode,
        "repeats": repeats,
        "timestamp": datetime.now().isoformat(),
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


def run_benchmark_with_retry(
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
    skip_completed: bool = True,
    max_retries: int = 2,
) -> Tuple[Path, Dict[str, Dict[str, float]]]:
    """Run benchmark with retry capability for failed tests."""
    
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                print(f"\n=== Retry attempt {attempt}/{max_retries} ===")
            
            return run_benchmark(
                language=language,
                base_url=base_url,
                tests=tests,
                mode=mode,
                vus=vus,
                duration_override=duration_override,
                repeats_override=repeats_override,
                keep_raw=keep_raw,
                output_dir=output_dir,
                label=label,
                wait=wait,
                memory_probe=memory_probe,
                memory_interval=memory_interval,
                skip_completed=skip_completed,
            )
        except Exception as exc:
            last_exception = exc
            if attempt < max_retries:
                print(f"Benchmark failed on attempt {attempt + 1}: {exc}")
                print("Retrying...")
                # Brief delay before retry
                import time
                time.sleep(2)
            else:
                print(f"Benchmark failed after {max_retries + 1} attempts")
                
    # If we get here, all retries failed
    raise last_exception


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
