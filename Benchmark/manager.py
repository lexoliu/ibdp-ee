#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REST manager to start and stop benchmark services on a remote host."""

from __future__ import annotations

import argparse
import json
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

from service_utils import kill_tree
from start_service import LOGS_DIR, start_language_service


def parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return default


class ServiceManager:
    """Track a single managed service process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process = None
        self._meta: Dict[str, Any] = {}

    def _is_process_alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def status(self) -> Dict[str, Any]:
        with self._lock:
            running = self._is_process_alive()
            payload = {
                "running": running,
                "meta": {**self._meta} if running else {},
            }
            if running:
                payload["meta"].setdefault("pid", self._process.pid if self._process else None)
            return payload

    def start(self, config: Dict[str, Any]) -> Dict[str, Any]:
        language = config.get("language")
        if not language:
            raise ValueError("'language' is required")

        host = config.get("host", "0.0.0.0")
        port = int(config.get("port", 8080))
        health_host = config.get("health_host") or config.get("healthHost") or "127.0.0.1"
        health_path = config.get("health_path") or config.get("healthPath") or "/echo"
        wait = parse_bool(config.get("wait"), True)
        ensure_free = parse_bool(config.get("ensure_free"), True)

        with self._lock:
            if self._is_process_alive():
                raise RuntimeError("Service already running")

            # Clean up exited process state if any.
            if self._process and self._process.poll() is not None:
                self._process = None
                self._meta = {}

            proc, log_path = start_language_service(
                language,
                host=host,
                port=port,
                health_host=health_host,
                health_path=health_path,
                wait=wait,
                ensure_free=ensure_free,
                log_dir=LOGS_DIR,
            )

            meta = {
                "language": language,
                "host": host,
                "port": port,
                "health_host": health_host,
                "health_path": health_path,
                "log_path": str(log_path),
                "started_at": time.time(),
                "pid": proc.pid,
            }
            self._process = proc
            self._meta = meta
            return meta

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            if not self._is_process_alive():
                # Nothing to stop
                self._process = None
                self._meta = {}
                return {"stopped": False}

            proc = self._process
            kill_tree(proc)
            try:
                proc.wait(timeout=10)
            except Exception:
                pass
            stopped_meta = {**self._meta, "stopped_at": time.time()}
            self._process = None
            self._meta = {}
            return {"stopped": True, "meta": stopped_meta}


MANAGER = ServiceManager()


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "BenchmarkManager/1.0"

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON payload: {exc}")

    def _send(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (http method name)
        if self.path == "/status":
            payload = MANAGER.status()
            self._send(HTTPStatus.OK, payload)
            return
        self._send(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            payload = self._read_json()
        except ValueError as exc:
            self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        if self.path == "/start":
            try:
                meta = MANAGER.start(payload)
            except ValueError as exc:
                self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            except RuntimeError as exc:
                self._send(HTTPStatus.CONFLICT, {"error": str(exc)})
                return
            except Exception as exc:
                self._send(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
                return
            self._send(HTTPStatus.OK, {"status": "started", "meta": meta})
            return

        if self.path == "/stop":
            meta = MANAGER.stop()
            self._send(HTTPStatus.OK, {"status": "stopped", **meta})
            return

        self._send(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def log_message(self, fmt: str, *args: Any) -> None:
        # Quieter logs; keep consistent formatting.
        message = fmt % args
        print(f"[manager] {self.address_string()} {self.command} {self.path} - {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark service manager")
    parser.add_argument("--bind", default="0.0.0.0", help="Interface to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=9000, help="Port to listen on (default: 9000)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.bind, args.port), RequestHandler)
    print(f"Service manager listening on http://{args.bind}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down manager ...")
    finally:
        server.shutdown()
        server.server_close()
        MANAGER.stop()


if __name__ == "__main__":
    main()
