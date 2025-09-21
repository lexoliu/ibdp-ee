#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Utilities for managing benchmark language services."""

from __future__ import annotations

import os
import shlex
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional


def popen(
    cmd: str,
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
    log_file: Optional[Path] = None,
    prefix: Optional[str] = None,
) -> subprocess.Popen:
    """Spawn a shell command with optional log teeing and prefixed stdout."""

    file_handle = None
    if log_file and prefix is None:
        file_handle = log_file.open("w")
    try:
        if prefix is None:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd) if cwd else None,
                env=env,
                shell=True,
                stdout=file_handle or subprocess.PIPE,
                stderr=subprocess.STDOUT if file_handle else subprocess.PIPE,
                preexec_fn=os.setsid if os.name != "nt" else None,
                text=True if file_handle is None else False,
            )
        else:
            log_handle = log_file.open("w") if log_file else None
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd) if cwd else None,
                env=env,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid if os.name != "nt" else None,
                text=True,
            )

            def _pump() -> None:
                assert proc.stdout is not None
                for line in proc.stdout:
                    if log_handle:
                        log_handle.write(line)
                        log_handle.flush()
                    sys.stdout.write(f"{prefix}{line}")
                    sys.stdout.flush()
                if log_handle:
                    log_handle.close()

            thread = threading.Thread(target=_pump, daemon=True)
            thread.start()
            setattr(proc, "_prefix_thread", thread)
    except Exception:
        if file_handle:
            file_handle.close()
        raise
    return proc


def kill_tree(proc: subprocess.Popen) -> None:
    if not proc:
        return
    try:
        if os.name == "nt":
            proc.terminate()
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        pass


def _candidate_hosts(host: Optional[str]) -> list[str]:
    if not host or host in {"0.0.0.0", "", "::"}:
        return ["127.0.0.1", "::1"]
    if host == "127.0.0.1":
        return [host]
    hosts = [host]
    if host not in {"127.0.0.1", "::1"}:
        hosts.append("127.0.0.1")
    return hosts


def port_busy(port: int, host: Optional[str] = None) -> bool:
    for candidate in _candidate_hosts(host):
        try:
            with socket.create_connection((candidate, port), timeout=0.2):
                return True
        except (OSError, ValueError):
            continue
    return False


def pids_on_port(port: int) -> list[int]:
    try:
        output = subprocess.check_output(
            f"lsof -iTCP:{port} -sTCP:LISTEN -n -P",
            shell=True,
            text=True,
        )
        return [int(line.split()[1]) for line in output.splitlines()[1:] if line.split()]
    except Exception:
        try:
            output = subprocess.check_output(
                f"fuser -n tcp {port}",
                shell=True,
                text=True,
                stderr=subprocess.DEVNULL,
            )
            return [int(pid) for pid in output.split() if pid.isdigit()]
        except Exception:
            try:
                output = subprocess.check_output(
                    ["ss", "-ltnp"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
                pids: list[int] = []
                needle = f":{port}"
                for line in output.splitlines():
                    if needle not in line:
                        continue
                    if "pid=" in line:
                        for segment in line.split():
                            if "pid=" in segment:
                                try:
                                    pid_text = segment.split("pid=")[1].split(",")[0]
                                    pids.append(int(pid_text))
                                except Exception:
                                    continue
                return pids
            except Exception:
                try:
                    output = subprocess.check_output(
                        f"netstat -ltnp | grep :{port}",
                        shell=True,
                        text=True,
                        stderr=subprocess.DEVNULL,
                    )
                    pids = []
                    for token in output.split():
                        if "/" in token and token.split("/")[0].isdigit():
                            pids.append(int(token.split("/")[0]))
                    return pids
                except Exception:
                    return []


def ensure_port_free(port: int = 8080, host: Optional[str] = None, wait_after_kill: float = 1.0) -> None:
    if not port_busy(port, host):
        return

    print(f"!! port {port} busy for host {host or '*'}, trying to free...")
    for pid in pids_on_port(port):
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass

    for _ in range(20):
        if not port_busy(port, host):
            print(f"-- port {port} is free (after SIGTERM)")
            return
        time.sleep(0.2)

    for pid in pids_on_port(port):
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass

    time.sleep(wait_after_kill)
    if port_busy(port, host):
        raise RuntimeError(f"port {port} still busy after SIGKILL")
    print(f"-- port {port} is free (after SIGKILL)")


def curl_post_echo_ok(url: str) -> bool:
    cmd = f"curl -fsS -X POST {shlex.quote(url)} -H 'Content-Type: text/plain' -d 'ok'"
    return subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def wait_for_health(
    base_url: str,
    health_path: str = "/echo",
    port: Optional[int] = None,
    host: Optional[str] = None,
    timeout: int = 120,
) -> bool:
    if port is not None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if port_busy(port, host):
                break
            time.sleep(0.2)
        else:
            return False

    start = time.time()
    while time.time() - start < timeout:
        if curl_post_echo_ok(base_url.rstrip("/") + health_path):
            return True
        time.sleep(1)
    return False

__all__ = [
    "popen",
    "kill_tree",
    "port_busy",
    "pids_on_port",
    "ensure_port_free",
    "curl_post_echo_ok",
    "wait_for_health",
]
