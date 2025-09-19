#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Start a single benchmark language service."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from service_utils import ensure_port_free, kill_tree, popen, wait_for_health

ROOT = Path(__file__).resolve().parent
JAVA_DIR = ROOT / "java"
GO_DIR = ROOT / "go"
RUST_DIR = ROOT / "rust"
LOGS_DIR = ROOT / "results" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def java_command(host: str, port: int) -> tuple[str, dict, Path]:
    jvm_args = "-Xms512m -Xmx1024m -XX:+UseG1GC -XX:+AlwaysPreTouch"
    cmd = (
        "mvn -q -DskipTests "
        f"-Dspring-boot.run.arguments=--server.port={port} "
        f"-Dspring-boot.run.jvmArguments='{jvm_args}' "
        "spring-boot:run"
    )
    env = os.environ.copy()
    return cmd, env, JAVA_DIR


def go_command(host: str, port: int) -> tuple[str, dict, Path]:
    env = os.environ.copy()
    env["SERVER_HOST"] = host
    env["SERVER_PORT"] = str(port)
    return "go run .", env, GO_DIR


def rust_command(host: str, port: int) -> tuple[str, dict, Path]:
    env = os.environ.copy()
    env["SERVER_HOST"] = host
    env["SERVER_PORT"] = str(port)
    return "cargo run --release", env, RUST_DIR


COMMANDS = {
    "java": java_command,
    "go": go_command,
    "rust": rust_command,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a benchmark language service.")
    parser.add_argument("language", choices=COMMANDS.keys(), help="Service to start")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    parser.add_argument("--health-host", default="127.0.0.1", help="Host to use for local health check")
    parser.add_argument("--health-path", default="/echo", help="Health check path (default: /echo)")
    parser.add_argument("--no-wait", action="store_true", help="Do not wait for health check")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    ensure_port_free(args.port)

    cmd_builder = COMMANDS[args.language]
    cmd, env, workdir = cmd_builder(args.host, args.port)

    log_path = LOGS_DIR / f"{args.language}_{int(time.time())}.log"
    print(f"Starting {args.language} service: {cmd}")

    proc = popen(cmd, cwd=workdir, env=env, log_file=log_path)

    try:
        if not args.no_wait:
            base_url = f"http://{args.health_host}:{args.port}"
            print("Waiting for service health ...")
            if not wait_for_health(base_url, health_path=args.health_path, port=args.port):
                kill_tree(proc)
                print("Health check failed", file=sys.stderr)
                return 1
            print(f"Service ready at http://{args.host}:{args.port}")

        print(f"Logs: {log_path}")
        print("Press Ctrl+C to stop.")
        proc.wait()
        return proc.returncode or 0
    except KeyboardInterrupt:
        print("Stopping service ...")
        kill_tree(proc)
        return 130


if __name__ == "__main__":
    sys.exit(main())
