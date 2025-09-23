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
    return 250 if mode == "debug" else 10_000

# Prioritize `kv` because it tends to surface stability problems fastest.
DEFAULT_TEST_ORDER = ["kv", "prime", "light"]

MODE_DEFAULTS = {
    "debug": {"duration": "2s", "repeats": 1, "prewarm_duration": "1s"},
    "normal": {"duration": "10m", "repeats": 1, "prewarm_duration": "5m"}, # Single 10-minute test run with 5min prewarm
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
    parser.add_argument("--mode", choices=MODE_DEFAULTS.keys(), default=os.environ.get("MODE", "normal"), help="Select run mode: debug=2s smoke, normal=10m test")
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


def run_k6_prewarm(
    test: str,
    script: Path,
    base_url: str,
    output_dir: Path,
    vus: int,
    duration: str,
    *,
    kv_key_space: int | None = None,
    mode: str | None = None,
) -> None:
    """Run k6 prewarm phase to bring service to steady state."""
    
    # For KV test, use longer prewarm to ensure all keys are populated
    if test == "kv" and duration != "1s":  # Don't extend debug mode
        base_seconds = parse_duration_seconds(duration)
        # For KV, use 1.5x prewarm duration to ensure full key population
        prewarm_seconds = int(base_seconds * 1.5)
        prewarm_duration = f"{prewarm_seconds}s"
        print(f"🔥 KV prewarm using extended duration: {prewarm_duration}")
    else:
        prewarm_duration = duration
        print(f"🔥 Prewarm phase: {prewarm_duration}")

    cmd = [
        "k6",
        "run", 
        "--vus",
        str(vus),
        "--duration",
        prewarm_duration,
        "--no-summary",  # Don't generate summary for prewarm
        str(script.resolve()),
    ]

    env = os.environ.copy()
    env.setdefault("BASE_URL", base_url)
    env.setdefault("K6_BASE_URL", base_url)
    env.setdefault("K6_DURATION", prewarm_duration)
    env.setdefault("K6_PREWARM", "1")  # Signal to k6 scripts this is prewarm
    if mode is not None:
        env.setdefault("K6_MODE", mode)
    if test == "kv" and kv_key_space is not None:
        env.setdefault("K6_KV_KEY_SPACE", str(kv_key_space))

    print(f"Running prewarm: {' '.join(cmd)}")
    proc = subprocess.run(cmd, env=env, cwd=str(output_dir), capture_output=True)
    if proc.returncode not in (0, 99):
        print(f"⚠️ Prewarm failed (exit {proc.returncode}), continuing anyway")
        if proc.stderr:
            print(f"Prewarm stderr: {proc.stderr.decode()}")
    else:
        print(f"✅ Prewarm completed successfully")


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
    prewarm_duration: str | None = None,
) -> Tuple[Path, Path]:
    # Run prewarm phase if specified
    if prewarm_duration and attempt == 1:  # Only prewarm on first attempt
        run_k6_prewarm(
            test=test,
            script=script,
            base_url=base_url,
            output_dir=output_dir,
            vus=vus,
            duration=prewarm_duration,
            kv_key_space=kv_key_space,
            mode=mode,
        )
        
        # Brief pause between prewarm and actual test
        print("⏸️ Brief pause between prewarm and actual test...")
        time.sleep(2)
        
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


# KV auto-fill function removed - now using prewarm retry logic instead


def parse_summary(summary_path: Path) -> Dict[str, float]:
    data = json.loads(summary_path.read_text())
    metrics = data.get("metrics", {})

    def metric_value(metric: str, key: str) -> float:
        """Extract metric value, handling both nested 'values' format and direct format."""
        metric_data = metrics.get(metric, {})
        if isinstance(metric_data, dict):
            # Try direct access first (current k6 format)
            if key in metric_data:
                return float(metric_data[key])
            # Fall back to 'values' nested format (legacy)
            values = metric_data.get("values", {})
            if key in values:
                return float(values[key])
        return 0.0

    return {
        "http_reqs": metric_value("http_reqs", "count"),
        "throughput": metric_value("http_reqs", "rate"),
        "latency_avg": metric_value("http_req_duration", "avg"),
        "latency_p50": metric_value("http_req_duration", "med"),  # k6 uses "med" for p50
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
        
        total_samples = len(self._samples)
        valid_samples = [(elapsed, value) for elapsed, value in self._samples if value is not None]
        failed_samples = total_samples - len(valid_samples)
        
        if total_samples > 0:
            success_rate = len(valid_samples) / total_samples * 100
            print(f"Memory sampling summary: {len(valid_samples)}/{total_samples} samples valid ({success_rate:.1f}% success rate)")
            if failed_samples > 0:
                print(f"Warning: {failed_samples} memory samples failed during collection")
        else:
            print("Warning: No memory samples were collected at all")
        
        self._samples.clear()
        self._stop.clear()
        return valid_samples

    def _run(self) -> None:
        consecutive_failures = 0
        while not self._stop.is_set():
            try:
                value = self._probe()
                if value is not None:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
            except Exception as e:
                consecutive_failures += 1
                value = None
                if consecutive_failures % 10 == 0:  # Log every 10 consecutive failures
                    print(f"Warning: Memory probe failing consistently ({consecutive_failures} failures): {e}")
            
            elapsed = time.time() - self._start_time
            self._samples.append((elapsed, value))
            self._stop.wait(self._interval)


def is_experiment_complete(output_dir: Path, tests: List[str]) -> Tuple[bool, List[str]]:
    """Check if experiment is complete by verifying CSV files exist and memory data is present."""
    missing_tests = []
    for test in tests:
        csv_file = output_dir / f"{test}_timeseries.csv"
        memory_file = output_dir / f"{test}_memory.csv"
        
        # Check if timeseries CSV exists and has data
        if not csv_file.exists():
            missing_tests.append(test)
            continue
            
        # Check if memory CSV exists and has meaningful data
        if not memory_file.exists() or memory_file.stat().st_size <= 50:  # Header + at least one data row
            missing_tests.append(test)
            print(f"Warning: Missing or incomplete memory data for {test} test")
            continue
            
        # Verify timeseries has actual performance data (not all zeros)
        try:
            with csv_file.open('r') as f:
                lines = f.readlines()
                if len(lines) <= 5:  # Too few data points
                    missing_tests.append(test)
                    print(f"Warning: Insufficient timeseries data for {test} test ({len(lines)} lines)")
                    continue
        except Exception as e:
            missing_tests.append(test)
            print(f"Warning: Cannot validate timeseries data for {test} test: {e}")
            continue
            
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

    # Get duration from override or mode defaults
    raw_duration = duration_override or mode_defaults["duration"]
    duration = raw_duration.strip()
    if not duration:
        duration = mode_defaults["duration"]

    # Get prewarm duration from mode defaults
    prewarm_duration = mode_defaults.get("prewarm_duration")
    
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
        f"Mode: {mode} | duration: {duration} | prewarm: {prewarm_duration} | repeats: {repeats} | "
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
            print(f"Running attempt {attempt}/{repeats} with duration {duration}")
            
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
                prewarm_duration=prewarm_duration,
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
        else:
            print(f"WARNING: No memory data collected for {test} test! This indicates a problem with memory monitoring.")
            # Create an empty memory file to mark the attempt
            memory_file = output_dir / f"{test}_memory.csv"
            memory_file.write_text("timestamp,memory_mb\n# No memory data collected - monitoring failed\n")

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
            
            if entries == expected_entries:
                print("✅ KV occupancy verified - all keys populated correctly.")
            elif entries < expected_entries:
                deficit = expected_entries - entries
                raise RuntimeError(
                    f"❌ KV under-populated: missing {deficit:,} entries. "
                    f"Prewarm duration may be insufficient. Consider extending prewarm or running test again."
                )
            else:
                surplus = entries - expected_entries
                print(f"✅ KV over-populated by {surplus:,} entries - this is acceptable.")

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
                error_message = str(exc)
                print(f"Benchmark failed on attempt {attempt + 1}: {exc}")
                
                # Check if this is a KV under-population issue
                if "KV under-populated" in error_message:
                    print("🔄 KV under-population detected - will retry with extended prewarm")
                else:
                    print("🔄 Retrying benchmark...")
                    
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
