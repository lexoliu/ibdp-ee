#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Orchestrate full benchmark workflow using the remote service manager."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Tuple
import urllib.error
import urllib.request

try:
    from plot_comparison import generate_plots
except ModuleNotFoundError as exc:
    missing_module = exc.name if getattr(exc, "name", None) else str(exc)
    print(
        f"Missing Python module '{missing_module}'. Run install_client.sh to install Python dependencies.",
        file=sys.stderr,
    )
    sys.exit(1)

from benchmark import DEFAULT_TEST_ORDER, MODE_DEFAULTS, run_benchmark

RESULTS_ROOT = Path(__file__).resolve().parent / "results"
DEFAULT_LANGUAGES = ["java", "go", "rust"]
HTTP_TIMEOUT = 120
REQUIRED_COMMANDS = ["python3", "k6"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run benchmarks across languages via the remote manager")
    parser.add_argument(
        "--languages",
        nargs="+",
        default=DEFAULT_LANGUAGES,
        help="Languages to benchmark (default: java go rust)",
    )
    parser.add_argument(
        "--tests",
        nargs="+",
        default=list(DEFAULT_TEST_ORDER),
        choices=list(DEFAULT_TEST_ORDER),
        help="k6 test suites to execute",
    )
    parser.add_argument(
        "--mode",
        choices=MODE_DEFAULTS.keys(),
        default="normal",
        help="Benchmark mode controlling duration and retries",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Shortcut for --mode debug (overrides --mode if provided)",
    )
    parser.add_argument("--vus", type=int, default=64, help="Number of virtual users (default: 64)")
    parser.add_argument(
        "--duration",
        default=None,
        help="Optional duration override passed to benchmark.py",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=None,
        help="Optional repeat override passed to benchmark.py",
    )
    parser.add_argument("--keep-raw", action="store_true", help="Keep raw k6 json outputs")
    parser.add_argument(
        "--label-prefix",
        default=None,
        help="Optional prefix for run labels stored in results.json",
    )

    parser.add_argument(
        "--manager-url",
        default=None,
        help="Service manager base URL. Defaults to http://<service-host>:<manager-port>",
    )
    parser.add_argument(
        "--manager-port",
        type=int,
        default=9000,
        help="Port used when deriving the manager URL (default: 9000)",
    )
    parser.add_argument("--service-host", default="0.0.0.0", help="Service bind host on manager side")
    parser.add_argument("--service-port", type=int, default=8080, help="Service bind port")
    parser.add_argument(
        "--health-host",
        default="127.0.0.1",
        help="Host the manager should use for health checks",
    )
    parser.add_argument("--health-path", default="/echo", help="Health check path (default: /echo)")

    parser.add_argument(
        "--client-host",
        default=None,
        help="Host clients use to reach the service (defaults to service host)",
    )
    parser.add_argument(
        "--client-port",
        type=int,
        default=None,
        help="Port clients use to reach the service (defaults to service port)",
    )
    parser.add_argument(
        "--base-url-template",
        default="http://{host}:{port}",
        help="Template used to compute the service base URL for k6",
    )
    parser.add_argument(
        "--fixed-base-url",
        default=None,
        help="Explicit base URL for all benchmarks (skips template rendering)",
    )

    parser.add_argument(
        "--plots-dir",
        type=Path,
        default=None,
        help="Directory for generated comparison plots (default: results/plots/<timestamp>)",
    )
    parser.add_argument("--skip-plots", action="store_true", help="Skip plot generation")
    parser.add_argument(
        "--manager-timeout",
        type=int,
        default=HTTP_TIMEOUT,
        help="Timeout for manager HTTP requests (default: 120s)",
    )
    parser.add_argument(
        "--memory-interval",
        type=float,
        default=1.0,
        help="Seconds between memory samples while a test is running (default: 1.0)",
    )

    return parser.parse_args()


def compute_base_url(args: argparse.Namespace, language: str) -> str:
    if args.fixed_base_url:
        template = args.fixed_base_url
    else:
        template = args.base_url_template
    host = args.client_host or args.service_host
    port = args.client_port or args.service_port
    return template.format(language=language, host=host, port=port)


def _json_request(url: str, *, method: str = "GET", payload: Dict[str, object] | None = None, timeout: int) -> Dict[str, object]:
    data = None
    if payload is not None:
        encoded = json.dumps(payload).encode("utf-8")
        data = encoded
    req = urllib.request.Request(url, data=data, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
            if not body:
                return {}
            return json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8")
        try:
            error_payload = json.loads(error_body)
            message = error_payload.get("error", error_body.strip())
        except json.JSONDecodeError:
            message = error_body.strip() or str(exc)
        raise RuntimeError(f"{method} {url} failed: {message} (status {exc.code})") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc}") from exc


def start_remote_service(args: argparse.Namespace, language: str) -> Dict[str, object]:
    payload = {
        "language": language,
        "host": args.service_host,
        "port": args.service_port,
        "health_host": args.health_host,
        "health_path": args.health_path,
        "wait": True,
        "ensure_free": True,
    }
    url = args.manager_url + "/start"
    print(f"Requesting start of {language} via {url}")
    response = _json_request(url, method="POST", payload=payload, timeout=args.manager_timeout)
    meta = response.get("meta")
    if not isinstance(meta, dict):
        raise RuntimeError("Manager response missing metadata")
    return meta


def stop_remote_service(args: argparse.Namespace) -> None:
    url = args.manager_url + "/stop"
    try:
        _json_request(url, method="POST", payload={}, timeout=args.manager_timeout)
    except RuntimeError as exc:
        print(f"Warning: failed to stop service cleanly: {exc}")


def make_memory_probe(args: argparse.Namespace) -> Callable[[], float | None]:
    status_url = args.manager_url + "/status"

    def probe() -> float | None:
        try:
            payload = _json_request(status_url, timeout=args.manager_timeout)
        except Exception:
            return None
        meta = payload.get("meta")
        if isinstance(meta, dict):
            value = meta.get("memory_mb")
            if isinstance(value, (int, float)):
                return float(value)
        return None

    return probe


def main() -> int:
    args = parse_args()
    missing = [cmd for cmd in REQUIRED_COMMANDS if shutil.which(cmd) is None]
    if missing:
        print(
            "Missing required commands: "
            + ", ".join(missing)
            + ". Run install_client.sh and ensure dependencies are installed.",
            file=sys.stderr,
        )
        return 1

    if args.manager_url:
        args.manager_url = args.manager_url.rstrip("/")
    else:
        host = args.service_host
        if host in {"0.0.0.0", "::", ""}:
            host = args.health_host or "127.0.0.1"
        args.manager_url = f"http://{host}:{args.manager_port}"

    status_url = args.manager_url + "/status"
    try:
        _json_request(status_url, timeout=args.manager_timeout)
    except RuntimeError as exc:
        print(
            f"Manager not reachable at {status_url}: {exc}. "
            "Ensure manager.py is running or adjust --manager-url/--manager-port.",
            file=sys.stderr,
        )
        return 1

    print(f"Using manager API at {args.manager_url}")

    if args.debug and args.mode != "debug":
        print("Debug flag provided; forcing mode=debug")
        args.mode = "debug"
    pipeline_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    plots_dir = args.plots_dir or (RESULTS_ROOT / "plots" / pipeline_id)
    memory_probe = make_memory_probe(args)
    run_entries: List[Tuple[str, Path]] = []

    for language in args.languages:
        base_url = compute_base_url(args, language)
        print(f"\n=== Benchmarking {language.upper()} ===")
        print(f"Using base URL: {base_url}")
        service_meta: Dict[str, object] | None = None
        try:
            service_meta = start_remote_service(args, language)
            label = f"{args.label_prefix}-{language}" if args.label_prefix else f"{language}-{args.mode}"
            output_dir, summary = run_benchmark(
                language,
                base_url,
                args.tests,
                mode=args.mode,
                vus=args.vus,
                duration_override=args.duration,
                repeats_override=args.repeats,
                keep_raw=args.keep_raw,
                label=label,
                memory_probe=memory_probe,
                memory_interval=args.memory_interval,
            )
            run_entries.append((language, output_dir))
        except Exception as exc:
            print(f"Error while benchmarking {language}: {exc}", file=sys.stderr)
            return 1
        finally:
            stop_remote_service(args)
            if service_meta:
                log_path = service_meta.get("log_path")
                if log_path:
                    print(f"Service log: {log_path}")

    if args.skip_plots:
        print("Skipping plot generation as requested")
        return 0

    print(f"\nGenerating plots in {plots_dir}")
    generate_plots(run_entries, args.tests, plots_dir, None, verbose=True)

    print("\nBenchmark workflow completed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
