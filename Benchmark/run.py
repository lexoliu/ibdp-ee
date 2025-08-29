#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基准跑法（固定使用已有 k6 脚本）：
- 顺序在 8080 端口启动 Java/Go/Rust（每次只跑一个）
- 依次跑 prime / light / kv 三组
- 采样 RSS 内存
- 生成三组图：吞吐(req/s)、平均延迟(ms)、内存(MB)

变更点：
- Java: mvn spring-boot:run
- Go:   go run .
- Rust: cargo run --release
- 启动前清理 8080（SIGTERM → SIGKILL）
- 健康检查仅使用 **POST /echo**
- 容忍 k6 阈值越界退出码 99（仍导出数据并继续流程）
"""

import os, sys, time, json, shlex, signal, threading, subprocess, socket, re
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# -------------------- 基本配置 --------------------
ROOT = Path(__file__).resolve().parent
JAVA_DIR = ROOT / "java"
GO_DIR   = ROOT / "go"
RUST_DIR = ROOT / "rust"
K6_DIR   = ROOT / "k6"
RESULTS  = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

# k6 脚本路径（使用你已有的文件）
K6_PRIME = K6_DIR / "prime.js"
K6_LIGHT = K6_DIR / "light.js"
K6_KV    = (K6_DIR / "kv.js") if (K6_DIR / "kv.js").exists() else (K6_DIR / "kv" / "kv.js")

# 压测参数
VUS      = int(os.environ.get("VUS", "64"))
DURATION = os.environ.get("DURATION", "60s")

BASE_URL   = "http://127.0.0.1:8080"
HEALTH_PATH= "/echo"            # 仅用 POST /echo 探活
K6_BIN     = "k6"               # 确保 PATH 能找到 k6

# -------------------- 工具函数 --------------------
def popen(cmd: str, cwd: Path=None, env=None, stdout=None, stderr=None):
    return subprocess.Popen(
        cmd, cwd=str(cwd) if cwd else None, env=env,
        shell=True, stdout=stdout, stderr=stderr,
        preexec_fn=os.setsid if os.name != 'nt' else None
    )

def kill_tree(p: subprocess.Popen):
    if not p: return
    try:
        if os.name == 'nt':
            p.terminate()
        else:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    except Exception:
        pass

def port_busy(port: int) -> bool:
    s = socket.socket(); s.settimeout(0.2)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()

def pids_on_port(port: int):
    try:
        out = subprocess.check_output(f"lsof -iTCP:{port} -sTCP:LISTEN -n -P", shell=True, text=True)
        return list({int(line.split()[1]) for line in out.splitlines()[1:] if line.split()})
    except Exception:
        try:
            out = subprocess.check_output(f"fuser -n tcp {port}", shell=True, text=True, stderr=subprocess.DEVNULL)
            return [int(x) for x in re.findall(r"\d+", out)]
        except Exception:
            return []

def ensure_port_free(port=8080, wait_after_kill=1.0):
    if not port_busy(port):
        return
    print(f"!! port {port} busy, trying to free...")
    pids = pids_on_port(port)
    for pid in pids:
        try: os.kill(pid, signal.SIGTERM)
        except Exception: pass
    for _ in range(20):
        if not port_busy(port):
            print(f"-- port {port} is free (after SIGTERM)")
            return
        time.sleep(0.2)
    # 强杀
    pids = pids_on_port(port)
    for pid in pids:
        try: os.kill(pid, signal.SIGKILL)
        except Exception: pass
    time.sleep(wait_after_kill)
    assert not port_busy(port), f"port {port} still busy after SIGKILL"
    print(f"-- port {port} is free (after SIGKILL)")

def curl_post_echo_ok(url: str) -> bool:
    cmd = f"curl -fsS -X POST {shlex.quote(url)} -H 'Content-Type: text/plain' -d 'ok'"
    return subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

def process_alive(p: subprocess.Popen) -> bool:
    return (p.poll() is None)

def wait_echo_health(base_url: str, path: str, proc: subprocess.Popen, log_path: Path,
                     port: int = 8080, port_wait: int = 60, timeout: int = 120) -> bool:
    start = time.time()
    # 等端口
    deadline = time.time() + port_wait
    while time.time() < deadline:
        if not process_alive(proc):
            print("!! process exited before port opened")
            return False
        if port_busy(port):
            break
        time.sleep(0.2)
    if not port_busy(port):
        return False
    # 轮询 POST /echo
    while time.time() - start < timeout:
        if not process_alive(proc):
            print("!! process exited during healthcheck")
            return False
        if curl_post_echo_ok(base_url + path):
            return True
        time.sleep(1)
    return False

def sample_rss(pid: int, out_csv: Path, stop_evt: threading.Event):
    with out_csv.open("w") as f:
        f.write("ts,rss_kb\n")
        while not stop_evt.is_set():
            try:
                proc = subprocess.run(f"ps -o rss= -p {pid}",
                                      shell=True, capture_output=True, text=True)
                rss = proc.stdout.strip() or "0"
                f.write(f"{int(time.time())},{rss}\n"); f.flush()
            except Exception:
                pass
            time.sleep(1)

def run_k6(script_path: Path, tag_prefix: str):
    json_out    = RESULTS / f"{tag_prefix}.k6.json"
    summary_out = RESULTS / f"{tag_prefix}.summary.json"
    env = os.environ.copy()
    env["K6_BASE_URL"] = BASE_URL
    env["VUS"] = str(VUS)
    env["DURATION"] = DURATION
    cmd = (
        f'{K6_BIN} run '
        f'--vus {VUS} --duration {DURATION} '
        f'--summary-export {shlex.quote(str(summary_out))} '
        f'--out json={shlex.quote(str(json_out))} '
        f'{shlex.quote(str(script_path))}'
    )
    print(f">> k6: {script_path.name}")
    proc = subprocess.run(cmd, shell=True, env=env)
    if proc.returncode not in (0, 99):
        raise RuntimeError(f"k6 failed: {script_path} (exit {proc.returncode})")
    if proc.returncode == 99:
        print(f"!! k6 thresholds breached for {script_path.name} (exit 99) — continuing")
    return json_out, summary_out

# 解析 k6 --out json
def parse_k6_timeseries(jsonl_path: Path):
    through, lat_sum, lat_cnt = {}, {}, {}
    with jsonl_path.open("r") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("type") != "Point": continue
            metric = obj.get("metric")
            data = obj.get("data", {})
            t = int(data.get("time", 0) // 1_000_000_000)
            val = data.get("value", None)
            if metric == "http_reqs":
                through[t] = through.get(t, 0) + 1
            elif metric == "http_req_duration" and val is not None:
                lat_sum[t] = lat_sum.get(t, 0.0) + float(val)
                lat_cnt[t] = lat_cnt.get(t, 0) + 1
    if not through and not lat_sum:
        return pd.DataFrame(), pd.DataFrame()
    idx = pd.Index(range(min(through.keys() or [0] + lat_sum.keys() or [0]),
                         max(through.keys() or [0] + lat_sum.keys() or [0]) + 1), name="sec")
    thr = pd.Series(through, name="throughput").reindex(idx, fill_value=0).to_frame()
    lat = pd.Series({t: lat_sum[t]/lat_cnt[t] for t in lat_sum}, name="latency_ms").reindex(idx).to_frame()
    return thr, lat

def load_mem(mem_csv: Path):
    df = pd.read_csv(mem_csv)
    df["sec"] = df["ts"]
    return df.set_index("sec")[["rss_kb"]]

def plot_group(group_title: str, series: dict):
    plt.rcParams.update({'figure.dpi': 140})
    fig1, ax1 = plt.subplots(); fig2, ax2 = plt.subplots(); fig3, ax3 = plt.subplots()
    for lang, paths in series.items():
        thr, lat = parse_k6_timeseries(paths["k6"])
        mem = load_mem(paths["mem"])
        s0 = min([df.index.min() for df in (thr, lat, mem) if not df.empty], default=0)
        if not thr.empty: ax1.plot(thr.index - s0, thr["throughput"], label=lang)
        if not lat.empty: ax2.plot(lat.index - s0, lat["latency_ms"], label=lang)
        if not mem.empty: ax3.plot(mem.index - s0, mem["rss_kb"]/1024.0, label=lang)
    ax1.set_title(f'{group_title}: Throughput'); ax1.set_ylabel('req/s'); ax1.legend()
    ax2.set_title(f'{group_title}: Latency'); ax2.set_ylabel('ms'); ax2.legend()
    ax3.set_title(f'{group_title}: Memory'); ax3.set_ylabel('MB'); ax3.legend()
    for ax in (ax1, ax2, ax3): ax.set_xlabel('Time (s)'); ax.grid(True)
    fig1.savefig(RESULTS / f'{group_title}_throughput.png')
    fig2.savefig(RESULTS / f'{group_title}_latency.png')
    fig3.savefig(RESULTS / f'{group_title}_memory.png')
    plt.close(fig1); plt.close(fig2); plt.close(fig3)

# -------------------- 启动命令 --------------------
def java_run_cmd() -> str:
    jvm_args = "-Xms512m -Xmx1024m -XX:+UseG1GC -XX:+AlwaysPreTouch"
    return ("mvn -q -DskipTests "
            f"-Dspring-boot.run.arguments=--server.port=8080 "
            f"-Dspring-boot.run.jvmArguments='{jvm_args}' "
            "spring-boot:run")

def go_run_cmd() -> str:
    return "go run ."

def rust_run_cmd() -> str:
    return "cargo run --release"

# -------------------- 主流程 --------------------
def bench_one(name: str, workdir: Path, run_cmd: str):
    ensure_port_free(8080)
    print(f"\n==== {name}: start on 8080 ====")
    log_path = RESULTS / f"{name}.log"
    proc = popen(run_cmd, cwd=workdir, stdout=log_path.open("w"), stderr=subprocess.STDOUT)
    print("Health check: waiting for POST /echo ...")
    if not wait_echo_health(BASE_URL, HEALTH_PATH, proc, log_path):
        kill_tree(proc); raise RuntimeError(f"{name} health check failed: POST {HEALTH_PATH}")
    out = {}
    try:
        for group, script in [("prime", K6_PRIME), ("light", K6_LIGHT), ("kv", K6_KV)]:
            print(f"-- {name} · {group} --")
            mem_csv = RESULTS / f"{name}_{group}_mem.csv"
            stop_evt = threading.Event()
            t = threading.Thread(target=sample_rss, args=(proc.pid, mem_csv, stop_evt), daemon=True); t.start()
            k6_json, _ = run_k6(script, f"{name}_{group}")
            stop_evt.set(); t.join(timeout=5)
            out[group] = {"k6": k6_json, "mem": mem_csv}
    finally:
        print(f"== stopping {name} ==")
        kill_tree(proc); time.sleep(2); ensure_port_free(8080)
    return out

def main():
    all_series = {"prime":{}, "light":{}, "kv":{}}
    if JAVA_DIR.exists(): r = bench_one("JAVA", JAVA_DIR, java_run_cmd()); [all_series[g].update({"JAVA": r[g]}) for g in r]
    if GO_DIR.exists():   r = bench_one("GO", GO_DIR, go_run_cmd());     [all_series[g].update({"GO": r[g]}) for g in r]
    if RUST_DIR.exists(): r = bench_one("RUST", RUST_DIR, rust_run_cmd()); [all_series[g].update({"RUST": r[g]}) for g in r]
    print("\n== plotting ==")
    for g in ["prime","light","kv"]:
        if all_series[g]: plot_group(g.upper(), all_series[g])
    print(f"\n✅ Done: {RESULTS}")

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: sys.exit(130)