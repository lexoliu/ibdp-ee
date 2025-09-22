#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Start a single benchmark language service."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict

from service_utils import curl_post_echo_ok, ensure_port_free, kill_tree, popen

ROOT = Path(__file__).resolve().parent
JAVA_DIR = ROOT / "java"
GO_DIR = ROOT / "go"
RUST_DIR = ROOT / "rust"
LOGS_DIR = ROOT / "results" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def java_command(host: str, port: int) -> tuple[str, dict, Path, Dict[str, Any]]:
    # Base JVM arguments
    jvm_args = "-Xms4g -Xmx24g -XX:+UseG1GC -XX:+AlwaysPreTouch"
    
    # Force enable GC logging for all benchmarks
    env = os.environ.copy()
    gc_log_path = LOGS_DIR / f"java_gc_{int(time.time())}.log"
    jvm_args += f" -Xlog:gc*:{gc_log_path}:time,level,tags"
    
    run_args = [
        f"--server.port={port}",
        f"--server.address={host if host not in {'0.0.0.0', '::', ''} else '0.0.0.0'}",
        "--spring.main.banner-mode=off",
        "--spring.main.log-startup-info=false",
        "--logging.level.root=error",
        "--logging.level.org.springframework=error",
        "--logging.level.reactor.netty=error",
    ]
    cmd = (
        "mvn -q -DskipTests "
        f"-Dspring-boot.run.arguments='{' '.join(run_args)}' "
        f"-Dspring-boot.run.jvmArguments='{jvm_args}' "
        "spring-boot:run"
    )
    env.setdefault("SERVER_LOG", "0")
    extras: Dict[str, Any] = {"gc_log_path": gc_log_path}
    return cmd, env, JAVA_DIR, extras


def go_command(host: str, port: int) -> tuple[str, dict, Path]:
    env = os.environ.copy()
    env["SERVER_HOST"] = host
    env["SERVER_PORT"] = str(port)
    env.setdefault("SERVER_LOG", "0")
    # Force enable GC tracing for all benchmarks
    env["GODEBUG"] = "gctrace=1"
    
    return "go run .", env, GO_DIR


def rust_command(host: str, port: int) -> tuple[str, dict, Path]:
    env = os.environ.copy()
    env["SERVER_HOST"] = host
    env["SERVER_PORT"] = str(port)
    env.setdefault("SERVER_LOG", "0")
    return "cargo run --release", env, RUST_DIR


COMMANDS = {
    "java": java_command,
    "go": go_command,
    "rust": rust_command,
}


def start_language_service(
    language: str,
    *,
    host: str = "0.0.0.0",
    port: int = 8080,
    health_host: str | None = None,
    health_path: str = "/echo",
    wait: bool = True,
    ensure_free: bool = True,
    log_dir: Path = LOGS_DIR,
) -> tuple[subprocess.Popen, Path, Dict[str, Any]]:
    """Start a service process and optionally wait for readiness."""

    if ensure_free:
        ensure_port_free(port, host=host)

    cmd_builder = COMMANDS[language]
    cmd_result = cmd_builder(host, port)
    try:
        cmd, env, workdir, extras = cmd_result  # type: ignore[misc]
    except ValueError:
        cmd, env, workdir = cmd_result  # type: ignore[misc]
        extras = {}
    env.setdefault("SERVER_HOST", host)
    env.setdefault("SERVER_PORT", str(port))
    
    # GC tracing is now forced enabled for all benchmarks

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{language}_{int(time.time())}.log"
    extras = dict(extras)
    if language == "go" and "gc_log_path" not in extras:
        extras["gc_log_path"] = log_path
    print(f"Starting {language} service: {cmd}")

    prefix = f"[{language}] "
    try:
        proc = popen(cmd, cwd=workdir, env=env, log_file=log_path, prefix=prefix)
    except Exception:
        raise

    if wait:
        effective_health_host = health_host or (host if host not in {"0.0.0.0", "::", ""} else "127.0.0.1")
        base_url = f"http://{effective_health_host}:{port}"
        target = base_url.rstrip("/") + health_path
        print(f"Waiting for service health at {target} ... (logs: {log_path})")

        deadline = time.time() + 120
        ready = False
        while time.time() < deadline:
            if proc.poll() is not None:
                kill_tree(proc)
                raise RuntimeError(
                    f"Service exited early with code {proc.returncode}. See logs: {log_path}"
                )
            if curl_post_echo_ok(target):
                ready = True
                break
            time.sleep(1)

        if not ready:
            kill_tree(proc)
            raise RuntimeError("Health check failed")
        print(f"Service ready at http://{host}:{port}")

    return proc, log_path, extras


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a benchmark language service.")
    parser.add_argument("language", choices=COMMANDS.keys(), help="Service to start")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    parser.add_argument("--health-host", default=None, help="Host to use for local health check (defaults to --host)")
    parser.add_argument("--health-path", default="/echo", help="Health check path (default: /echo)")
    parser.add_argument("--no-wait", action="store_true", help="Do not wait for health check")
    parser.add_argument("--disable-gc-trace", action="store_true", help="Disable GC tracing (enabled by default)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    
    # Set environment variable for GC tracing (enabled by default)
    if not args.disable_gc_trace:
        os.environ["ENABLE_GC_TRACE"] = "1"

    try:
        proc, log_path, extras = start_language_service(
            args.language,
            host=args.host,
            port=args.port,
            health_host=args.health_host,
            health_path=args.health_path,
            wait=not args.no_wait,
            ensure_free=True,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        print(f"Logs: {log_path}")
        gc_log_path = extras.get("gc_log_path")
        if gc_log_path and gc_log_path != log_path:
            print(f"GC logs: {gc_log_path}")
        print("Press Ctrl+C to stop.")
        proc.wait()
        return proc.returncode or 0
    except KeyboardInterrupt:
        print("Stopping service ...")
        kill_tree(proc)
        return 130


if __name__ == "__main__":
    sys.exit(main())
